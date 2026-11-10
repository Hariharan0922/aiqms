import re
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import uuid4

from app.services.ingestion.base import ExtractedDocument, ExtractedParagraph


@dataclass
class ExtractedSection:
    section_id: str
    section_number: Optional[str]
    section_title: str
    parent_section_id: Optional[str]
    level: int
    section_order: int
    content_text: str = ""
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    subsections: list["ExtractedSection"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "section_number": self.section_number,
            "section_title": self.section_title,
            "parent_section_id": self.parent_section_id,
            "level": self.level,
            "section_order": self.section_order,
            "content_text": self.content_text,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "subsections": [s.to_dict() for s in self.subsections],
        }


class StructureExtractor:
    """Logical document structure and hierarchy extractor."""

    NUMBERED_HEADING_REGEX = re.compile(r"^\s*(\d+(\.\d+)*[\.\)]?)\s+(.*)$")
    UNNUMBERED_HEADING_KEYWORDS = {
        "purpose", "scope", "reference", "references", "reference documents",
        "reference documents/ standard", "reference documents/standard",
        "responsibility", "responsibilities", "procedure", "procedures",
        "records", "records/formats", "revision history", "definitions",
        "terms and definitions", "annexure", "index", "foreword", "introduction",
        "executive summary", "quality policy", "quality manual"
    }

    def extract_structure(self, doc: ExtractedDocument) -> list[ExtractedSection]:
        raw_sections: list[ExtractedSection] = []
        current_section: Optional[ExtractedSection] = None
        section_order = 0

        # Stack to track active parent at each level: {level: section_id}
        level_stack: dict[int, str] = {}

        # Initial preamble/header section for content before the first heading
        preamble = ExtractedSection(
            section_id=f"SEC-{uuid4().hex[:8].upper()}",
            section_number=None,
            section_title="Preamble / Header",
            parent_section_id=None,
            level=1,
            section_order=section_order,
            page_start=1 if doc.file_format == "PDF" else None,
            page_end=1 if doc.file_format == "PDF" else None,
        )
        current_section = preamble

        in_index_block = False
        index_seen_titles: set[str] = set()

        for idx, p in enumerate(doc.paragraphs):
            text = p.text.strip()
            if not text:
                continue

            is_h, sec_num, sec_title, level = self._analyze_heading(p)

            # Check if this is the start of an INDEX block
            if is_h and sec_title.upper() == "INDEX":
                in_index_block = True
                if current_section and current_section.content_text.strip():
                    raw_sections.append(current_section)
                section_order += 1
                sec_id = f"SEC-{uuid4().hex[:8].upper()}"
                current_section = ExtractedSection(
                    section_id=sec_id,
                    section_number=None,
                    section_title="INDEX",
                    parent_section_id=None,
                    level=1,
                    section_order=section_order,
                    page_start=p.page_number,
                    page_end=p.page_number,
                )
                level_stack[1] = sec_id
                continue

            # If we are inside an INDEX block
            if in_index_block:
                # Check if this heading has following body text or if it repeats the first index item
                next_p = doc.paragraphs[idx + 1] if idx + 1 < len(doc.paragraphs) else None
                next_has_body = next_p is not None and not next_p.is_heading and len(next_p.text.strip()) > 20

                if is_h and (next_has_body or text.endswith(":") or (sec_title.lower() in index_seen_titles)):
                    # Index block has ended; start the real section!
                    in_index_block = False
                else:
                    # Append index item to INDEX section content
                    index_seen_titles.add(sec_title.lower())
                    if current_section:
                        if current_section.content_text:
                            current_section.content_text += "\n" + text
                        else:
                            current_section.content_text = text
                    continue

            if is_h:
                if current_section == preamble and not preamble.content_text.strip():
                    pass
                elif current_section:
                    raw_sections.append(current_section)

                section_order += 1
                sec_id = f"SEC-{uuid4().hex[:8].upper()}"

                # Determine parent from stack
                parent_id = None
                for l in range(level - 1, 0, -1):
                    if l in level_stack:
                        parent_id = level_stack[l]
                        break

                level_stack[level] = sec_id
                for l in list(level_stack.keys()):
                    if l > level:
                        del level_stack[l]

                current_section = ExtractedSection(
                    section_id=sec_id,
                    section_number=sec_num,
                    section_title=sec_title,
                    parent_section_id=parent_id,
                    level=level,
                    section_order=section_order,
                    page_start=p.page_number,
                    page_end=p.page_number,
                )
            else:
                if current_section:
                    if current_section.content_text:
                        current_section.content_text += "\n\n" + text
                    else:
                        current_section.content_text = text

                    if p.page_number:
                        if not current_section.page_start:
                            current_section.page_start = p.page_number
                        current_section.page_end = p.page_number

        # Append last active section
        if current_section and (current_section != preamble or preamble.content_text.strip()):
            raw_sections.append(current_section)

        # Distribute document tables to sections based on page or order
        self._attach_tables_to_sections(doc, raw_sections)

        # Normalize section order indices
        for i, s in enumerate(raw_sections):
            s.section_order = i + 1

        return raw_sections

    def build_tree(self, flat_sections: list[ExtractedSection]) -> list[ExtractedSection]:
        """Build hierarchical nested tree from flat ordered sections."""
        id_map: dict[str, ExtractedSection] = {s.section_id: s for s in flat_sections}
        root_sections: list[ExtractedSection] = []

        for s in flat_sections:
            s.subsections = []

        for s in flat_sections:
            if s.parent_section_id and s.parent_section_id in id_map:
                id_map[s.parent_section_id].subsections.append(s)
            else:
                root_sections.append(s)

        return root_sections

    def _analyze_heading(self, p: ExtractedParagraph) -> tuple[bool, Optional[str], str, int]:
        text = p.text.strip()
        num_match = self.NUMBERED_HEADING_REGEX.match(text)

        if num_match and len(text) < 140:
            raw_num = num_match.group(1).rstrip(".").rstrip(")")
            raw_title = num_match.group(3).strip()
            if raw_title:
                if p.heading_level > 0:
                    level = p.heading_level
                else:
                    parts = [int(x) for x in raw_num.split(".") if x.isdigit()]
                    if len(parts) == 2 and parts[1] == 0:
                        level = 1
                    else:
                        level = min(len(parts), 4)
                return True, raw_num, raw_title, level

        # Check explicit heading tag from extractor
        if p.is_heading:
            clean_title = text.rstrip(":").strip()
            level = p.heading_level if p.heading_level > 0 else 1
            return True, None, clean_title, level

        # Check common unnumbered keywords
        lower = text.rstrip(":").strip().lower()
        if lower in self.UNNUMBERED_HEADING_KEYWORDS:
            return True, None, text.rstrip(":").strip(), 1

        if text.startswith("CHAPTER") and len(text) < 40:
            return True, None, text, 1

        return False, None, text, 1

    def _attach_tables_to_sections(self, doc: ExtractedDocument, sections: list[ExtractedSection]) -> None:
        if not sections or not doc.tables:
            return

        for tbl in doc.tables:
            md = tbl.to_markdown()
            if not md:
                continue

            target_section = None
            if tbl.page_number:
                for s in reversed(sections):
                    if s.page_start and s.page_end and s.page_start <= tbl.page_number <= s.page_end:
                        target_section = s
                        break
            if not target_section:
                # Attach to last section
                target_section = sections[-1]

            if target_section.content_text:
                target_section.content_text += "\n\n" + md
            else:
                target_section.content_text = md
