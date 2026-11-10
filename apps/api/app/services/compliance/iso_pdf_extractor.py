"""ISO 13485:2016 PDF Knowledge Base Extractor.

Extracts complete clause hierarchy, titles, requirement content, explanatory notes,
and source page references from ISO-13485-2016-EN.pdf.
"""

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import re
from typing import Dict, List, Optional
try:
    import pdfplumber
except ImportError:
    pdfplumber = None


@dataclass
class ExtractedISOClause:
    clause_id: str
    clause_number: str
    parent_clause_number: Optional[str]
    level: int
    title: str
    category: str
    clause_text: str
    normative_text: str
    explanatory_notes: Optional[str]
    is_normative: bool
    summary_requirements: str
    requires_documented_procedure: bool
    requires_record: bool
    page_start: int
    page_end: int
    content_hash: str
    subclauses: List[str] = field(default_factory=list)


class ISOPdfExtractor:
    """Authoritative parser and hierarchy builder for ISO 13485:2016 standard PDF."""

    KNOWN_CLAUSE_MAP = {
        "1": ("Scope", "Scope", 1),
        "2": ("Normative references", "Normative references", 1),
        "3": ("Terms and definitions", "Terms and definitions", 1),
        "4": ("Quality management system", "Quality management system", 1),
        "4.1": ("General requirements", "Quality management system", 2),
        "4.2": ("Documentation requirements", "Quality management system", 2),
        "4.2.1": ("General", "Quality management system", 3),
        "4.2.2": ("Quality manual", "Quality management system", 3),
        "4.2.3": ("Medical device file", "Quality management system", 3),
        "4.2.4": ("Control of documents", "Quality management system", 3),
        "4.2.5": ("Control of records", "Quality management system", 3),
        "5": ("Management responsibility", "Management responsibility", 1),
        "5.1": ("Management commitment", "Management responsibility", 2),
        "5.2": ("Customer focus", "Management responsibility", 2),
        "5.3": ("Quality policy", "Management responsibility", 2),
        "5.4": ("Planning", "Management responsibility", 2),
        "5.4.1": ("Quality objectives", "Management responsibility", 3),
        "5.4.2": ("Quality management system planning", "Management responsibility", 3),
        "5.5": ("Responsibility, authority and communication", "Management responsibility", 2),
        "5.5.1": ("Responsibility and authority", "Management responsibility", 3),
        "5.5.2": ("Management representative", "Management responsibility", 3),
        "5.5.3": ("Internal communication", "Management responsibility", 3),
        "5.6": ("Management review", "Management responsibility", 2),
        "5.6.1": ("General", "Management responsibility", 3),
        "5.6.2": ("Review input", "Management responsibility", 3),
        "5.6.3": ("Review output", "Management responsibility", 3),
        "6": ("Resource management", "Resource management", 1),
        "6.1": ("Provision of resources", "Resource management", 2),
        "6.2": ("Human resources", "Resource management", 2),
        "6.3": ("Infrastructure", "Resource management", 2),
        "6.4": ("Work environment and contamination control", "Resource management", 2),
        "6.4.1": ("Work environment", "Resource management", 3),
        "6.4.2": ("Contamination control", "Resource management", 3),
        "7": ("Product realization", "Product realization", 1),
        "7.1": ("Planning of product realization", "Product realization", 2),
        "7.2": ("Customer-related processes", "Product realization", 2),
        "7.2.1": ("Determination of requirements related to product", "Product realization", 3),
        "7.2.2": ("Review of requirements related to product", "Product realization", 3),
        "7.2.3": ("Communication", "Product realization", 3),
        "7.3": ("Design and development", "Product realization", 2),
        "7.3.1": ("General", "Product realization", 3),
        "7.3.2": ("Design and development planning", "Product realization", 3),
        "7.3.3": ("Design and development inputs", "Product realization", 3),
        "7.3.4": ("Design and development outputs", "Product realization", 3),
        "7.3.5": ("Design and development review", "Product realization", 3),
        "7.3.6": ("Design and development verification", "Product realization", 3),
        "7.3.7": ("Design and development validation", "Product realization", 3),
        "7.3.8": ("Design and development transfer", "Product realization", 3),
        "7.3.9": ("Control of design and development changes", "Product realization", 3),
        "7.3.10": ("Design and development files", "Product realization", 3),
        "7.4": ("Purchasing", "Product realization", 2),
        "7.4.1": ("Purchasing process", "Product realization", 3),
        "7.4.2": ("Purchasing information", "Product realization", 3),
        "7.4.3": ("Verification of purchased product", "Product realization", 3),
        "7.5": ("Production and service provision", "Product realization", 2),
        "7.5.1": ("Control of production and service provision", "Product realization", 3),
        "7.5.2": ("Cleanliness of product", "Product realization", 3),
        "7.5.3": ("Installation activities", "Product realization", 3),
        "7.5.4": ("Servicing activities", "Product realization", 3),
        "7.5.5": ("Particular requirements for sterile medical devices", "Product realization", 3),
        "7.5.6": ("Validation of processes for production and service provision", "Product realization", 3),
        "7.5.7": ("Particular requirements for validation of processes for sterilization and sterile barrier systems", "Product realization", 3),
        "7.5.8": ("Identification", "Product realization", 3),
        "7.5.9": ("Traceability", "Product realization", 3),
        "7.5.9.1": ("General", "Product realization", 4),
        "7.5.9.2": ("Particular requirements for implantable medical devices", "Product realization", 4),
        "7.5.10": ("Customer property", "Product realization", 3),
        "7.5.11": ("Preservation of product", "Product realization", 3),
        "7.6": ("Control of monitoring and measuring equipment", "Product realization", 2),
        "8": ("Measurement, analysis and improvement", "Measurement, analysis and improvement", 1),
        "8.1": ("General", "Measurement, analysis and improvement", 2),
        "8.2": ("Monitoring and measurement", "Measurement, analysis and improvement", 2),
        "8.2.1": ("Feedback", "Measurement, analysis and improvement", 3),
        "8.2.2": ("Complaint handling", "Measurement, analysis and improvement", 3),
        "8.2.3": ("Reporting to regulatory authorities", "Measurement, analysis and improvement", 3),
        "8.2.4": ("Internal audit", "Measurement, analysis and improvement", 3),
        "8.2.5": ("Monitoring and measurement of processes", "Measurement, analysis and improvement", 3),
        "8.2.6": ("Monitoring and measurement of product", "Measurement, analysis and improvement", 3),
        "8.3": ("Control of nonconforming product", "Measurement, analysis and improvement", 2),
        "8.3.1": ("General", "Measurement, analysis and improvement", 3),
        "8.3.2": ("Actions in response to nonconforming product detected before delivery", "Measurement, analysis and improvement", 3),
        "8.3.3": ("Actions in response to nonconforming product detected after delivery", "Measurement, analysis and improvement", 3),
        "8.3.4": ("Rework", "Measurement, analysis and improvement", 3),
        "8.4": ("Analysis of data", "Measurement, analysis and improvement", 2),
        "8.5": ("Improvement", "Measurement, analysis and improvement", 2),
        "8.5.1": ("General", "Measurement, analysis and improvement", 3),
        "8.5.2": ("Corrective action", "Measurement, analysis and improvement", 3),
        "8.5.3": ("Preventive action", "Measurement, analysis and improvement", 3),
    }

    # Clause 3 Terms definitions
    TERM_DEFINITIONS = {
        "3.1": "advisory notice",
        "3.2": "authorized representative",
        "3.3": "clinical evaluation",
        "3.4": "complaint",
        "3.5": "distributor",
        "3.6": "implantable medical device",
        "3.7": "labelling",
        "3.8": "life-cycle",
        "3.9": "manufacturer",
        "3.10": "medical device",
        "3.11": "medical device family",
        "3.12": "performance evaluation",
        "3.13": "post-market surveillance",
        "3.14": "product",
        "3.15": "purchased product",
        "3.16": "risk",
        "3.17": "risk management",
        "3.18": "sterile barrier system",
        "3.19": "sterile medical device",
        "3.20": "unique device identifier",
    }

    def __init__(self, pdf_path: Optional[str | Path] = None):
        if pdf_path:
            self.pdf_path = Path(pdf_path)
        else:
            # Check standard workspace location
            candidate = Path(__file__).resolve().parents[4] / "sample_documents" / "ISO-13485-2016-EN.pdf"
            if not candidate.exists():
                candidate = Path(__file__).resolve().parents[5] / "sample_documents" / "ISO-13485-2016-EN.pdf"
            if not candidate.exists():
                candidate = Path("sample_documents") / "ISO-13485-2016-EN.pdf"
            self.pdf_path = candidate

    def extract_clauses(self) -> List[ExtractedISOClause]:
        """Extract all clauses and subclauses from the ISO 13485:2016 PDF."""
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"ISO 13485 source PDF not found at {self.pdf_path}")

        with pdfplumber.open(self.pdf_path) as pdf:
            clean_lines = []
            # Extract standard normative clauses across pages 9 to 35 (0-indexed 8 to 34)
            for page_idx in range(8, min(35, len(pdf.pages))):
                page_num = page_idx + 1
                page_text = pdf.pages[page_idx].extract_text() or ""
                for raw_line in page_text.split("\n"):
                    s = raw_line.strip()
                    if not s:
                        continue
                    # Skip standard running header and footer artifacts
                    if s in [
                        "ISO 13485:2016(E)",
                        "INTERNATIONAL STANDARD ISO 13485:2016(E)",
                    ]:
                        continue
                    if "ISO 2016" in s and "rights reserved" in s:
                        continue
                    if re.match(r"^[0-9]+$", s):  # footer page number
                        continue
                    clean_lines.append((page_num, s))

        # Detect heading positions in clean lines
        heading_re = re.compile(r"^([1-8](?:\.[0-9]+){0,3})\s+(.*)$")
        heading_indices = []
        for idx, (pno, line) in enumerate(clean_lines):
            m = heading_re.match(line)
            if m:
                c_num = m.group(1)
                if c_num in self.KNOWN_CLAUSE_MAP:
                    title, category, level = self.KNOWN_CLAUSE_MAP[c_num]
                    heading_indices.append((idx, pno, c_num, title, category, level))

        # Sort heading occurrences in document order
        heading_indices.sort(key=lambda x: x[0])

        extracted: List[ExtractedISOClause] = []
        for i in range(len(heading_indices)):
            line_idx, p_start, c_num, title, category, level = heading_indices[i]
            next_idx = heading_indices[i + 1][0] if i + 1 < len(heading_indices) else len(clean_lines)
            p_end = clean_lines[next_idx - 1][0] if next_idx > line_idx else p_start

            # Collect body text lines
            body_parts: List[str] = []
            for j in range(line_idx + 1, next_idx):
                line_text = clean_lines[j][1]
                # Skip title wrap line for 7.5.7
                if c_num == "7.5.7" and j == line_idx + 1 and "barrier systems" in line_text:
                    continue
                # For terms (3.1 to 3.20), skip the title line if already captured
                if c_num.startswith("3.") and j == line_idx + 1 and line_text.lower() == title.lower():
                    continue
                body_parts.append(line_text)

            full_text = " ".join(body_parts).strip()

            # Separate normative requirement text from explanatory NOTE blocks
            notes_list: List[str] = []
            normative_parts: List[str] = []

            note_pattern = re.compile(
                r"(\bNOTE(?:\s+[0-9]+)?(?:\s+to\s+entry)?\s*[:\s])", re.IGNORECASE
            )
            parts = note_pattern.split(full_text)
            normative_parts.append(parts[0].strip())
            k = 1
            while k < len(parts):
                prefix = parts[k]
                note_content = parts[k + 1] if k + 1 < len(parts) else ""
                notes_list.append(f"{prefix}{note_content}".strip())
                k += 2

            normative_text = " ".join(normative_parts).strip()
            explanatory_notes = "\n\n".join(notes_list) if notes_list else None

            # Detect procedure and record requirements
            doc_proc = bool(
                re.search(
                    r"\b(?:documented\s+procedures?|document\s+procedures?|procedures?\s+shall\s+be\s+documented|shall\s+document\s+(?:[a-z]+\s+)?procedures?|shall\s+document\s+requirements)\b",
                    full_text,
                    re.IGNORECASE,
                )
            )
            rec = bool(
                re.search(
                    r"\b(?:records?\s+(?:[a-z0-9,()]+\s+){0,15}shall\s+be\s+maintained|maintain\s+records?|shall\s+maintain\s+(?:[a-z0-9,()]+\s+){0,10}records?|records?\s+shall\s+be\s+retained|shall\s+be\s+maintained\s+\(see\s+4\.2\.5\))\b",
                    full_text,
                    re.IGNORECASE,
                )
            )

            # Compute parent clause
            parent_num = self._get_parent_clause_number(c_num)

            # Determine whether clause is normative requirement or definitions/reference
            is_normative = c_num.split(".")[0] in ["4", "5", "6", "7", "8", "1"]

            # Content hash
            hash_input = f"{c_num}|{title}|{full_text}"
            content_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

            # Generate concise summary bullets
            summary = self._generate_summary_requirements(c_num, title, normative_text or full_text, doc_proc, rec)

            extracted.append(
                ExtractedISOClause(
                    clause_id=f"ISO-13485-{c_num}",
                    clause_number=c_num,
                    parent_clause_number=parent_num,
                    level=level,
                    title=title,
                    category=category,
                    clause_text=full_text,
                    normative_text=normative_text or full_text,
                    explanatory_notes=explanatory_notes,
                    is_normative=is_normative,
                    summary_requirements=summary,
                    requires_documented_procedure=doc_proc,
                    requires_record=rec,
                    page_start=p_start,
                    page_end=p_end,
                    content_hash=content_hash,
                )
            )

        # Build subclauses list for each parent clause
        clause_dict = {c.clause_number: c for c in extracted}
        for c in extracted:
            if c.parent_clause_number and c.parent_clause_number in clause_dict:
                clause_dict[c.parent_clause_number].subclauses.append(c.clause_number)

        return extracted

    @staticmethod
    def _get_parent_clause_number(clause_num: str) -> Optional[str]:
        parts = clause_num.split(".")
        if len(parts) <= 1:
            return None
        return ".".join(parts[:-1])

    @staticmethod
    def _generate_summary_requirements(
        clause_num: str, title: str, text: str, requires_proc: bool, requires_rec: bool
    ) -> str:
        """Create structured summary bullets for compliance traceability."""
        bullets = [f"- {title}"]
        if requires_proc:
            bullets.append("- Documented procedure is required")
        if requires_rec:
            bullets.append("- Records of conformity must be maintained")

        # Extract sentences with 'shall' for key requirement highlights
        shall_matches = re.findall(r"([^.]*?\bshall\b[^.]*?\.)", text, flags=re.IGNORECASE)
        for m in shall_matches[:3]:
            cleaned = " ".join(m.split()).strip()
            if len(cleaned) > 20 and len(cleaned) < 220:
                bullets.append(f"- {cleaned}")

        return "\n".join(bullets)
