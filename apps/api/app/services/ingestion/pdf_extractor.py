import re
from pathlib import Path
from typing import Optional
try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from app.services.ingestion.base import (
    BaseDocumentExtractor,
    ExtractedDocument,
    ExtractedHeaderFooter,
    ExtractedParagraph,
    ExtractedTable,
)


class PdfExtractor(BaseDocumentExtractor):
    """Extraction service for PDF documents using pdfplumber."""

    NUMBERED_HEADING_REGEX = re.compile(r"^\s*(\d+(\.\d+)*)\s+([A-Z].*)$")
    COMMON_QMS_HEADINGS = {
        "foreword", "introduction", "scope", "normative references",
        "terms and definitions", "quality management system",
        "management responsibility", "resource management", "product realization",
        "measurement, analysis and improvement", "purpose", "responsibilities",
        "procedure", "records", "annexure", "revision history"
    }

    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".pdf"

    def extract(self, file_path: Path) -> ExtractedDocument:
        if not file_path.exists():
            return ExtractedDocument(
                filename=file_path.name,
                file_format="PDF",
                total_pages=0,
                errors=[f"File not found: {file_path.name}"],
            )

        if file_path.stat().st_size == 0:
            return ExtractedDocument(
                filename=file_path.name,
                file_format="PDF",
                total_pages=0,
                errors=["Document is empty (0 bytes)."],
            )

        try:
            with open(file_path, "rb") as f:
                header = f.read(5)
                if not header.startswith(b"%PDF"):
                    return ExtractedDocument(
                        filename=file_path.name,
                        file_format="PDF",
                        total_pages=0,
                        errors=["Invalid or corrupted PDF: Missing %PDF signature."],
                    )
        except Exception as exc:
            return ExtractedDocument(
                filename=file_path.name,
                file_format="PDF",
                total_pages=0,
                errors=[f"Cannot read file: {str(exc)}"],
            )

        try:
            pdf = pdfplumber.open(file_path)
        except Exception as exc:
            return ExtractedDocument(
                filename=file_path.name,
                file_format="PDF",
                total_pages=0,
                errors=[f"Corrupted or unreadable PDF: {str(exc)}"],
            )

        extracted_paras: list[ExtractedParagraph] = []
        extracted_tables: list[ExtractedTable] = []
        page_texts: dict[int, str] = {}
        raw_text_parts: list[str] = []
        warnings: list[str] = []

        total_pages = len(pdf.pages)
        if total_pages == 0:
            pdf.close()
            return ExtractedDocument(
                filename=file_path.name,
                file_format="PDF",
                total_pages=0,
                errors=["PDF contains 0 pages."],
            )

        order_index = 0
        table_counter = 0
        total_text_chars = 0
        pages_with_no_text = 0

        for page_idx, page in enumerate(pdf.pages):
            page_number = page_idx + 1
            page_raw_text = page.extract_text() or ""
            page_raw_text = page_raw_text.strip()
            page_texts[page_number] = page_raw_text
            total_text_chars += len(page_raw_text)

            if not page_raw_text:
                pages_with_no_text += 1

            # Extract tables from page
            try:
                tables = page.extract_tables() or []
                for tbl_data in tables:
                    cleaned_rows = []
                    for row in tbl_data:
                        if not row:
                            continue
                        cleaned_row = [(c or "").strip().replace("\n", " ") for c in row]
                        if any(c for c in cleaned_row):
                            cleaned_rows.append(cleaned_row)

                    if cleaned_rows:
                        headers = cleaned_rows[0]
                        rows = cleaned_rows[1:] if len(cleaned_rows) > 1 else []
                        ext_tbl = ExtractedTable(
                            table_index=table_counter,
                            headers=headers,
                            rows=rows,
                            page_number=page_number,
                        )
                        extracted_tables.append(ext_tbl)
                        table_counter += 1
                        md = ext_tbl.to_markdown()
                        if md:
                            raw_text_parts.append(f"[Page {page_number}]\n" + md)
            except Exception as tbl_err:
                warnings.append(f"Table extraction notice on page {page_number}: {str(tbl_err)}")

            # Extract paragraphs from page text lines
            lines = page_raw_text.split("\n")
            current_para_lines: list[str] = []

            for line in lines:
                line_str = line.strip()
                if not line_str:
                    if current_para_lines:
                        para_text = " ".join(current_para_lines)
                        is_h, h_lvl = self._detect_pdf_heading(para_text)
                        extracted_paras.append(
                            ExtractedParagraph(
                                text=para_text,
                                is_heading=is_h,
                                heading_level=h_lvl,
                                page_number=page_number,
                                order_index=order_index,
                            )
                        )
                        order_index += 1
                        current_para_lines = []
                    continue

                is_h, _ = self._detect_pdf_heading(line_str)
                if is_h and current_para_lines:
                    # Flush previous paragraph before starting heading
                    para_text = " ".join(current_para_lines)
                    is_prev_h, prev_lvl = self._detect_pdf_heading(para_text)
                    extracted_paras.append(
                        ExtractedParagraph(
                            text=para_text,
                            is_heading=is_prev_h,
                            heading_level=prev_lvl,
                            page_number=page_number,
                            order_index=order_index,
                        )
                    )
                    order_index += 1
                    current_para_lines = [line_str]
                else:
                    current_para_lines.append(line_str)

            if current_para_lines:
                para_text = " ".join(current_para_lines)
                is_h, h_lvl = self._detect_pdf_heading(para_text)
                extracted_paras.append(
                    ExtractedParagraph(
                        text=para_text,
                        is_heading=is_h,
                        heading_level=h_lvl,
                        page_number=page_number,
                        order_index=order_index,
                    )
                )
                order_index += 1

            if page_raw_text:
                raw_text_parts.append(f"[Page {page_number}]\n{page_raw_text}")

        pdf.close()

        # Check for scanned or image-only PDF
        is_scanned = False
        ocr_required = False
        avg_chars_per_page = total_text_chars / total_pages if total_pages > 0 else 0

        if total_text_chars == 0 or (total_pages > 1 and avg_chars_per_page < 30 and pages_with_no_text >= total_pages // 2):
            is_scanned = True
            ocr_required = True
            warnings.append(
                "Scanned or image-only PDF detected (no text layer found). OCR is required to extract full content."
            )

        return ExtractedDocument(
            filename=file_path.name,
            file_format="PDF",
            total_pages=total_pages,
            paragraphs=extracted_paras,
            tables=extracted_tables,
            header_footer=ExtractedHeaderFooter(),
            raw_text="\n\n".join(raw_text_parts),
            is_scanned=is_scanned,
            ocr_required=ocr_required,
            warnings=warnings,
            page_texts=page_texts,
        )

    def _detect_pdf_heading(self, text: str) -> tuple[bool, int]:
        clean = text.strip()
        if len(clean) > 120 or not clean:
            return False, 0

        # Ignore running headers e.g. "ISO 13485:2016(E)" or "Page 12 of 44"
        if re.match(r"^ISO\s*\d+.*\(E\)", clean, re.IGNORECASE) or re.match(r"^Page\s*\d+", clean, re.IGNORECASE):
            return False, 0

        # Numbered headings like "4. Quality management system" or "4.2 Documentation requirements"
        num_match = self.NUMBERED_HEADING_REGEX.match(clean)
        if num_match:
            dots = num_match.group(1).count(".")
            return True, min(dots + 1, 4)

        # Standard clauses or chapters
        lower = clean.rstrip(":").strip().lower()
        if lower in self.COMMON_QMS_HEADINGS:
            return True, 1

        if clean.isupper() and len(clean) >= 4 and len(clean) <= 60 and not clean.endswith("."):
            return True, 2

        return False, 0
