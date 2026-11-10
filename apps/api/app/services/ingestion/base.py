from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class ExtractedTable:
    table_index: int
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    page_number: Optional[int] = None
    caption: Optional[str] = None

    def to_markdown(self) -> str:
        """Convert table to standard markdown representation for chunking."""
        if not self.rows and not self.headers:
            return ""
        lines = []
        if self.headers:
            lines.append("| " + " | ".join(self.headers) + " |")
            lines.append("| " + " | ".join(["---"] * len(self.headers)) + " |")
        for row in self.rows:
            # Pad row if headers are longer
            row_cells = list(row)
            if self.headers and len(row_cells) < len(self.headers):
                row_cells.extend([""] * (len(self.headers) - len(row_cells)))
            lines.append("| " + " | ".join(row_cells) + " |")
        return "\n".join(lines)


@dataclass
class ExtractedParagraph:
    text: str
    style_name: str = "Normal"
    is_heading: bool = False
    heading_level: int = 0
    is_list_item: bool = False
    list_type: Optional[str] = None  # "bullet" or "numbered"
    page_number: Optional[int] = None
    section_index: int = 0
    order_index: int = 0


@dataclass
class ExtractedHeaderFooter:
    header_text: str = ""
    footer_text: str = ""
    header_tables: list[ExtractedTable] = field(default_factory=list)
    footer_tables: list[ExtractedTable] = field(default_factory=list)


@dataclass
class ExtractedDocument:
    filename: str
    file_format: str
    total_pages: int
    paragraphs: list[ExtractedParagraph] = field(default_factory=list)
    tables: list[ExtractedTable] = field(default_factory=list)
    header_footer: ExtractedHeaderFooter = field(default_factory=ExtractedHeaderFooter)
    raw_text: str = ""
    is_scanned: bool = False
    ocr_required: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    page_texts: dict[int, str] = field(default_factory=dict)


class BaseDocumentExtractor(ABC):
    """Abstract base class for document format extractors."""

    @abstractmethod
    def extract(self, file_path: Path) -> ExtractedDocument:
        """Extract text, structure, tables, and headers/footers from document."""
        pass

    @abstractmethod
    def can_handle(self, file_path: Path) -> bool:
        """Check if extractor supports this file."""
        pass
