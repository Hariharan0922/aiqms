import re
from dataclasses import dataclass, field
from typing import Any, Optional
from app.services.ingestion.base import ExtractedDocument, ExtractedTable


@dataclass
class MetadataExtractionResult:
    document_title: Optional[str] = None
    document_number: Optional[str] = None
    revision: Optional[str] = None
    effective_date: Optional[str] = None
    review_date: Optional[str] = None
    department: Optional[str] = None
    document_owner: Optional[str] = None
    prepared_by: Optional[str] = None
    reviewed_by: Optional[str] = None
    approved_by: Optional[str] = None
    purpose: Optional[str] = None
    scope: Optional[str] = None
    responsibilities: Optional[str] = None
    confidence_scores: dict[str, float] = field(default_factory=dict)
    source_snippets: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_title": self.document_title,
            "document_number": self.document_number,
            "revision": self.revision,
            "effective_date": self.effective_date,
            "review_date": self.review_date,
            "department": self.department,
            "document_owner": self.document_owner,
            "prepared_by": self.prepared_by,
            "reviewed_by": self.reviewed_by,
            "approved_by": self.approved_by,
            "purpose": self.purpose,
            "scope": self.scope,
            "responsibilities": self.responsibilities,
            "confidence_scores": self.confidence_scores,
            "source_snippets": self.source_snippets,
        }


class MetadataExtractor:
    """Configurable rules-based metadata extraction for QMS documents."""

    DOC_NUM_PATTERNS = [
        re.compile(r"(?:DOCUMENT\s*(?:NO|NUMBER)|DOC\s*(?:NO|ID)|REF(?:ERENCE)?\s*(?:NO|NUMBER)?)\s*[:.\-]?\s*([A-Za-z0-9/_-]{3,40})", re.IGNORECASE),
        re.compile(r"\b(ETPL/[A-Za-z0-9/_-]{2,30})\b", re.IGNORECASE),
        re.compile(r"\b(ISO\s*13485(?::\d{4})?(?:\([A-Z]\))?)\b", re.IGNORECASE),
    ]

    REV_PATTERNS = [
        re.compile(r"(?:REVISION\s*(?:NO\.?|NUMBER)|REV\s*NO\.?)\s*[:.\-]?\s*([A-Za-z0-9._-]{1,15})", re.IGNORECASE),
        re.compile(r"\b((?:First|Second|Third|Fourth|Fifth|Sixth)\s+edition)\b", re.IGNORECASE),
        re.compile(r"\bRev(?:ision)?\s*[:.\-]\s*([A-Za-z0-9._-]{1,10})\b", re.IGNORECASE),
        re.compile(r"\bRev(?:ision)?\s+(\d+(?:\.\d+)?|[A-Z])\b", re.IGNORECASE),
    ]

    DATE_PATTERNS = [
        re.compile(r"(?:EFFECTIVE\s*DATE|EFF\s*DATE|DATE\s*OF\s*EFFECT)\s*[:.\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{2}[/-]\d{2})", re.IGNORECASE),
        re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
        re.compile(r"\b(\d{2}/\d{2}/\d{4})\b"),
    ]

    REVIEW_DATE_PATTERNS = [
        re.compile(r"(?:NEXT\s*REVIEW\s*DATE|REVIEW\s*DATE|DUE\s*DATE)\s*[:.\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{2}[/-]\d{2})", re.IGNORECASE),
    ]

    def extract_metadata(self, doc: ExtractedDocument) -> MetadataExtractionResult:
        result = MetadataExtractionResult()

        # Step 1: For PDF, inspect cover page (page 1) first
        if doc.file_format == "PDF":
            self._extract_from_pdf_cover(doc, result)

        # Step 2: Extract from header tables (highest confidence for QMS DOCX)
        self._extract_from_header_tables(doc, result)

        # Step 3: Extract from document body tables (sign-off / approval tables)
        self._extract_from_body_tables(doc, result)

        # Step 4: Extract from first page / title block
        self._extract_from_title_block(doc, result)

        # Step 5: Extract from regex scans across raw text for any remaining nulls
        self._extract_from_raw_text(doc, result)

        # Step 6: Extract Purpose, Scope, Responsibilities from section text
        self._extract_narrative_sections(doc, result)

        # Step 7: Validate and record warnings for missing essential metadata
        self._audit_completeness(result)

        return result

    def _extract_from_pdf_cover(self, doc: ExtractedDocument, result: MetadataExtractionResult) -> None:
        p1_text = doc.page_texts.get(1, "")
        if not p1_text:
            return

        # ISO standard documents
        iso_match = re.search(r"Medical devices\s*[–—-]\s*Quality\s*management systems\s*[–—-]\s*Requirements for regulatory purposes", p1_text, re.IGNORECASE)
        if iso_match:
            result.document_title = "Medical devices — Quality management systems — Requirements for regulatory purposes"
            result.confidence_scores["document_title"] = 0.98
            result.source_snippets["document_title"] = f"Cover page: '{iso_match.group(0)}'"

        ref_match = re.search(r"Reference number\s*\n?\s*(ISO\s*13485(?::\d{4})?(?:\([A-Z]\))?)", p1_text, re.IGNORECASE)
        if ref_match:
            result.document_number = ref_match.group(1).strip()
            result.confidence_scores["document_number"] = 0.98
            result.source_snippets["document_number"] = f"Cover page reference: '{ref_match.group(0)}'"
        elif re.search(r"\bISO\s*13485(?::\d{4})?\b", p1_text):
            m = re.search(r"\b(ISO\s*13485(?::\d{4})?)\b", p1_text)
            if m:
                result.document_number = m.group(1).strip()
                result.confidence_scores["document_number"] = 0.95
                result.source_snippets["document_number"] = f"Cover page text: '{m.group(0)}'"

        ed_match = re.search(r"\b((?:First|Second|Third|Fourth|Fifth)\s+edition)\b", p1_text, re.IGNORECASE)
        if ed_match:
            result.revision = ed_match.group(1).strip()
            result.confidence_scores["revision"] = 0.98
            result.source_snippets["revision"] = f"Cover page edition: '{ed_match.group(0)}'"

        dt_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", p1_text)
        if dt_match:
            result.effective_date = dt_match.group(1).strip()
            result.confidence_scores["effective_date"] = 0.95
            result.source_snippets["effective_date"] = f"Cover page date: '{dt_match.group(0)}'"

        # Check for other PDF headers e.g. "Complaint handling DOCUMENT NO. ETPL/F/15"
        for line in p1_text.split("\n")[:5]:
            if "DOCUMENT NO" in line.upper():
                doc_m = re.search(r"DOCUMENT\s*NO\.?\s*([A-Za-z0-9/_-]+)", line, re.IGNORECASE)
                if doc_m and not result.document_number:
                    result.document_number = doc_m.group(1).strip()
                    result.confidence_scores["document_number"] = 0.95
                    result.source_snippets["document_number"] = f"Cover line: '{line}'"
                title_part = line.split("DOCUMENT")[0].strip()
                if title_part and not result.document_title:
                    result.document_title = title_part
                    result.confidence_scores["document_title"] = 0.90
                    result.source_snippets["document_title"] = f"Cover line: '{line}'"

    def _extract_from_header_tables(self, doc: ExtractedDocument, result: MetadataExtractionResult) -> None:
        all_header_tables = doc.header_footer.header_tables
        for ht in all_header_tables:
            all_rows = []
            if ht.headers:
                all_rows.append(ht.headers)
            all_rows.extend(ht.rows)

            for row in all_rows:
                row_str = " | ".join(row)
                for i, cell in enumerate(row):
                    cell_clean = cell.strip()
                    cell_upper = cell_clean.upper()

                    # Title detection in header table
                    if ("STANDARD OPERATING" in cell_upper or "DEVICE MASTER" in cell_upper or "PROCEDURE FOR" in cell_upper) and not result.document_title:
                        result.document_title = cell_clean
                        result.confidence_scores["document_title"] = 0.98
                        result.source_snippets["document_title"] = f"Header table: '{cell_clean}'"

                    # Document Number
                    if "DOCUMENT NO" in cell_upper or "DOC NO" in cell_upper:
                        val = self._find_value_in_row_or_cell(cell, row, i)
                        if val and not result.document_number:
                            result.document_number = val
                            result.confidence_scores["document_number"] = 0.98
                            result.source_snippets["document_number"] = f"Header table row: '{row_str}'"

                    # Revision Number
                    if "REVISION NO" in cell_upper or "REV NO" in cell_upper:
                        val = self._find_value_in_row_or_cell(cell, row, i)
                        if val and not result.revision:
                            result.revision = val
                            result.confidence_scores["revision"] = 0.98
                            result.source_snippets["revision"] = f"Header table row: '{row_str}'"

                    # Effective Date
                    if "EFFECTIVE DATE" in cell_upper or "EFF DATE" in cell_upper:
                        val = self._find_value_in_row_or_cell(cell, row, i)
                        if val and not result.effective_date:
                            result.effective_date = val
                            result.confidence_scores["effective_date"] = 0.98
                            result.source_snippets["effective_date"] = f"Header table row: '{row_str}'"

    def _extract_from_body_tables(self, doc: ExtractedDocument, result: MetadataExtractionResult) -> None:
        for tbl in doc.tables[:3]:
            all_rows = []
            if tbl.headers:
                all_rows.append(tbl.headers)
            all_rows.extend(tbl.rows)

            for row in all_rows:
                if not row:
                    continue
                first_cell = row[0].strip().lower()
                row_str = " | ".join(row)

                if "prepared by" in first_cell and len(row) >= 2 and not result.prepared_by:
                    name = row[1].strip()
                    if name:
                        result.prepared_by = name
                        result.confidence_scores["prepared_by"] = 0.95
                        result.source_snippets["prepared_by"] = f"Approval table: '{row_str}'"
                        if len(row) >= 3 and not result.department:
                            designation = row[2].strip()
                            if "quality" in designation.lower() or "regulatory" in designation.lower():
                                result.department = "QA/RA"
                                result.confidence_scores["department"] = 0.85
                                result.source_snippets["department"] = f"Sign-off designation: '{designation}'"
                        if len(row) >= 5 and not result.effective_date:
                            date_str = row[4].strip()
                            if re.match(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", date_str):
                                result.effective_date = date_str
                                result.confidence_scores["effective_date"] = 0.90
                                result.source_snippets["effective_date"] = f"Prepared date: '{date_str}'"

                elif "reviewed by" in first_cell and len(row) >= 2 and not result.reviewed_by:
                    name = row[1].strip()
                    if name:
                        result.reviewed_by = name
                        result.confidence_scores["reviewed_by"] = 0.95
                        result.source_snippets["reviewed_by"] = f"Approval table: '{row_str}'"

                elif "approved by" in first_cell and len(row) >= 2 and not result.approved_by:
                    name = row[1].strip()
                    if name:
                        result.approved_by = name
                        result.confidence_scores["approved_by"] = 0.95
                        result.source_snippets["approved_by"] = f"Approval table: '{row_str}'"

    def _extract_from_title_block(self, doc: ExtractedDocument, result: MetadataExtractionResult) -> None:
        early_paras = [p.text.strip() for p in doc.paragraphs[:12] if p.text.strip()]
        if not result.document_title and early_paras:
            for p in early_paras:
                p_upper = p.upper()
                if "INDEX" in p_upper or p_upper == "ISO" or p.isdigit() or len(p) > 150:
                    continue
                if any(k in p_upper for k in ["STANDARD OPERATING PROCEDURE", "DEVICE MASTER FILE", "INTERNATIONAL STANDARD", "PROCEDURE FOR", "QUALITY MANUAL"]):
                    result.document_title = p
                    result.confidence_scores["document_title"] = 0.90
                    result.source_snippets["document_title"] = f"Title block: '{p}'"
                    break

    def _extract_from_raw_text(self, doc: ExtractedDocument, result: MetadataExtractionResult) -> None:
        sample_text = doc.raw_text[:5000]

        if not result.document_number:
            for pat in self.DOC_NUM_PATTERNS:
                m = pat.search(sample_text)
                if m:
                    result.document_number = m.group(1).strip()
                    result.confidence_scores["document_number"] = 0.85
                    result.source_snippets["document_number"] = f"Text match: '{m.group(0)}'"
                    break

        if not result.revision:
            for pat in self.REV_PATTERNS:
                m = pat.search(sample_text)
                if m:
                    cand = m.group(1).strip()
                    if cand.lower() not in {"or", "and", "the", "of", "for", "in", "to", "is", "a", "author", "date"}:
                        result.revision = cand
                        result.confidence_scores["revision"] = 0.85
                        result.source_snippets["revision"] = f"Text match: '{m.group(0)}'"
                        break

        if not result.effective_date:
            for pat in self.DATE_PATTERNS:
                m = pat.search(sample_text)
                if m:
                    result.effective_date = m.group(1).strip()
                    result.confidence_scores["effective_date"] = 0.80
                    result.source_snippets["effective_date"] = f"Text match: '{m.group(0)}'"
                    break

        if not result.review_date:
            for pat in self.REVIEW_DATE_PATTERNS:
                m = pat.search(sample_text)
                if m:
                    result.review_date = m.group(1).strip()
                    result.confidence_scores["review_date"] = 0.80
                    result.source_snippets["review_date"] = f"Text match: '{m.group(0)}'"
                    break

        if not result.document_owner:
            owner_m = re.search(r"(?:Document Owner|Owner)\s*[:.\-]\s*([A-Za-z\s.]+)(?:\n|$)", sample_text, re.IGNORECASE)
            if owner_m:
                result.document_owner = owner_m.group(1).strip()
                result.confidence_scores["document_owner"] = 0.80
                result.source_snippets["document_owner"] = f"Text match: '{owner_m.group(0)}'"

    def _extract_narrative_sections(self, doc: ExtractedDocument, result: MetadataExtractionResult) -> None:
        paras = doc.paragraphs
        for i, p in enumerate(paras):
            text_strip = p.text.strip()
            text_lower = text_strip.lower()

            # Purpose
            if not result.purpose and (text_lower.startswith("purpose:") or text_lower == "purpose"):
                content = []
                if ":" in text_strip and len(text_strip.split(":", 1)[1].strip()) > 10:
                    content.append(text_strip.split(":", 1)[1].strip())
                else:
                    for next_p in paras[i + 1 : i + 5]:
                        if next_p.is_heading or not next_p.text.strip():
                            break
                        content.append(next_p.text.strip())
                if content:
                    full_purpose = " ".join(content)
                    result.purpose = full_purpose
                    result.confidence_scores["purpose"] = 0.90
                    result.source_snippets["purpose"] = full_purpose[:150]

            # Scope
            if not result.scope and (text_lower.startswith("scope:") or text_lower == "scope" or text_lower == "1 scope" or text_lower.startswith("1 scope ")):
                content = []
                if ":" in text_strip and len(text_strip.split(":", 1)[1].strip()) > 10:
                    content.append(text_strip.split(":", 1)[1].strip())
                else:
                    for next_p in paras[i + 1 : i + 5]:
                        if next_p.is_heading or not next_p.text.strip():
                            break
                        content.append(next_p.text.strip())
                if content:
                    full_scope = " ".join(content)
                    result.scope = full_scope
                    result.confidence_scores["scope"] = 0.90
                    result.source_snippets["scope"] = full_scope[:150]

            # Responsibilities
            if not result.responsibilities and (text_lower.startswith("responsibility:") or text_lower == "responsibility" or text_lower == "responsibilities"):
                content = []
                for next_p in paras[i + 1 : i + 8]:
                    if next_p.heading_level == 1 or next_p.text.strip().lower() in ["procedure", "6. procedure", "records"]:
                        break
                    if next_p.text.strip():
                        content.append(next_p.text.strip())
                if content:
                    full_resp = "\n".join(content)
                    result.responsibilities = full_resp
                    result.confidence_scores["responsibilities"] = 0.85
                    result.source_snippets["responsibilities"] = full_resp[:150]

    def _find_value_in_row_or_cell(self, cell: str, row: list[str], i: int) -> Optional[str]:
        # Check if cell has both label and value separated by colon or dash
        m = re.search(r"(?:NO\.?|NUMBER|DATE)\s*[:.\-]\s*([A-Za-z0-9/_-]+.*)$", cell, re.IGNORECASE)
        if m:
            v = m.group(1).strip()
            if len(v) > 0 and v not in {".", ":", "-"}:
                return v
        # Otherwise look in next cell in row
        if i + 1 < len(row):
            nxt = row[i + 1].strip()
            if nxt and nxt not in {".", ":", "-"}:
                return nxt
        return None

    def _audit_completeness(self, result: MetadataExtractionResult) -> None:
        if not result.document_title:
            result.warnings.append("Document title could not be identified with confidence.")
        if not result.document_number:
            result.warnings.append("Document number is not identified in the document.")
        if not result.revision:
            result.warnings.append("Document revision number is not identified in the document.")
        if not result.effective_date:
            result.warnings.append("Effective date is not identified in the document.")
