import re
import zipfile
from pathlib import Path
from typing import Optional
import docx
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.services.ingestion.base import (
    BaseDocumentExtractor,
    ExtractedDocument,
    ExtractedHeaderFooter,
    ExtractedParagraph,
    ExtractedTable,
)


class DocxExtractor(BaseDocumentExtractor):
    """Extraction service for DOCX documents."""

    NUMBERED_HEADING_REGEX = re.compile(r"^\s*(\d+(\.\d+)*)\s+([A-Z].*)$")
    UNNUMBERED_HEADING_REGEX = re.compile(r"^\s*([A-Za-z][A-Za-z0-9\s/–-]{1,60}):?\s*$")
    LIST_ITEM_REGEX = re.compile(r"^\s*(\d+[\.\)]|\u2022|\*|\-)\s+(.*)$")

    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".docx"

    def extract(self, file_path: Path) -> ExtractedDocument:
        if not file_path.exists():
            return ExtractedDocument(
                filename=file_path.name,
                file_format="DOCX",
                total_pages=0,
                errors=[f"File not found: {file_path.name}"],
            )

        if file_path.stat().st_size == 0:
            return ExtractedDocument(
                filename=file_path.name,
                file_format="DOCX",
                total_pages=0,
                errors=["Document is empty (0 bytes)."],
            )

        try:
            doc = docx.Document(file_path)
        except (docx.opc.exceptions.PackageNotFoundError, zipfile.BadZipFile, Exception) as exc:
            return ExtractedDocument(
                filename=file_path.name,
                file_format="DOCX",
                total_pages=0,
                errors=[f"Corrupted or invalid DOCX document: {str(exc)}"],
            )

        extracted_paras: list[ExtractedParagraph] = []
        extracted_tables: list[ExtractedTable] = []
        raw_text_parts: list[str] = []
        warnings: list[str] = []

        # Extract headers and footers from all sections
        header_footer = self._extract_header_footer(doc)

        # Iterate document body elements in exact sequential order
        order_index = 0
        table_index = 0

        for child in doc.element.body:
            if isinstance(child, CT_P):
                p = Paragraph(child, doc)
                text = p.text.strip()
                if not text:
                    continue

                style_name = p.style.name if p.style else "Normal"
                is_heading, heading_level = self._detect_heading(p, text, style_name)
                is_list_item, list_type = self._detect_list(p, text, style_name)

                para = ExtractedParagraph(
                    text=text,
                    style_name=style_name,
                    is_heading=is_heading,
                    heading_level=heading_level,
                    is_list_item=is_list_item,
                    list_type=list_type,
                    order_index=order_index,
                )
                extracted_paras.append(para)
                raw_text_parts.append(text)
                order_index += 1

            elif isinstance(child, CT_Tbl):
                tbl = Table(child, doc)
                ext_table = self._extract_table(tbl, table_index)
                if ext_table.rows or ext_table.headers:
                    extracted_tables.append(ext_table)
                    md = ext_table.to_markdown()
                    if md:
                        raw_text_parts.append(md)
                    table_index += 1
                    order_index += 1

        if not extracted_paras and not extracted_tables:
            warnings.append("Document contains no readable paragraphs or tables.")

        raw_text = "\n\n".join(raw_text_parts)

        return ExtractedDocument(
            filename=file_path.name,
            file_format="DOCX",
            total_pages=1,  # DOCX files do not have intrinsic page boundaries before rendering
            paragraphs=extracted_paras,
            tables=extracted_tables,
            header_footer=header_footer,
            raw_text=raw_text,
            warnings=warnings,
        )

    def _detect_heading(self, p: Paragraph, text: str, style_name: str) -> tuple[bool, int]:
        style_lower = style_name.lower()
        if "heading 1" in style_lower or style_lower == "title":
            return True, 1
        if "heading 2" in style_lower:
            return True, 2
        if "heading 3" in style_lower:
            return True, 3
        if "heading" in style_lower:
            match = re.search(r"heading\s*(\d+)", style_lower)
            level = int(match.group(1)) if match else 1
            return True, level

        # Check numbered heading pattern, e.g. "1. Purpose" or "4.2 Documentation requirements"
        num_match = self.NUMBERED_HEADING_REGEX.match(text)
        if num_match and len(text) < 120:
            dots = num_match.group(1).count(".")
            return True, dots + 1

        # Check all bold runs
        is_all_bold = False
        if p.runs and len(text) < 80:
            is_all_bold = all(run.bold for run in p.runs if run.text.strip())
            if is_all_bold:
                return True, 2

        # Check common QMS unnumbered section headers
        common_qms_headers = {
            "purpose", "scope", "reference", "references", "responsibility",
            "responsibilities", "procedure", "procedures", "records", "records/formats",
            "revision history", "definitions", "annexure", "index"
        }
        clean_header = text.rstrip(":").strip().lower()
        if clean_header in common_qms_headers or clean_header.startswith("chapter"):
            return True, 1

        return False, 0

    def _detect_list(self, p: Paragraph, text: str, style_name: str) -> tuple[bool, Optional[str]]:
        style_lower = style_name.lower()
        if "bullet" in style_lower or "list" in style_lower:
            return True, "bullet"
        if "number" in style_lower:
            return True, "numbered"

        match = self.LIST_ITEM_REGEX.match(text)
        if match:
            prefix = match.group(1)
            if prefix.endswith(".") or prefix.endswith(")"):
                return True, "numbered"
            return True, "bullet"

        return False, None

    def _extract_table(self, tbl: Table, table_index: int) -> ExtractedTable:
        rows_data: list[list[str]] = []
        for row in tbl.rows:
            # Deduplicate horizontal cell text for merged cells
            seen_cells = []
            row_texts = []
            for cell in row.cells:
                # cell._tc is the underlying XML element
                if cell._tc not in seen_cells:
                    seen_cells.append(cell._tc)
                    row_texts.append(cell.text.strip().replace("\n", " "))
            if any(t for t in row_texts):
                rows_data.append(row_texts)

        if not rows_data:
            return ExtractedTable(table_index=table_index)

        headers = rows_data[0]
        data_rows = rows_data[1:] if len(rows_data) > 1 else []
        return ExtractedTable(table_index=table_index, headers=headers, rows=data_rows)

    def _extract_header_footer(self, doc: docx.Document) -> ExtractedHeaderFooter:
        hf = ExtractedHeaderFooter()
        h_texts = []
        f_texts = []
        header_tables = []
        footer_tables = []

        for section in doc.sections:
            # Header text and tables
            for p in section.header.paragraphs:
                t = p.text.strip()
                if t and t not in h_texts:
                    h_texts.append(t)
            for ht_idx, ht in enumerate(section.header.tables):
                ext_t = self._extract_table(ht, ht_idx)
                if ext_t.headers or ext_t.rows:
                    header_tables.append(ext_t)

            # Footer text and tables
            for p in section.footer.paragraphs:
                t = p.text.strip()
                if t and t not in f_texts:
                    f_texts.append(t)
            for ft_idx, ft in enumerate(section.footer.tables):
                ext_t = self._extract_table(ft, ft_idx)
                if ext_t.headers or ext_t.rows:
                    footer_tables.append(ext_t)

        hf.header_text = "\n".join(h_texts)
        hf.footer_text = "\n".join(f_texts)
        hf.header_tables = header_tables
        hf.footer_tables = footer_tables
        return hf
