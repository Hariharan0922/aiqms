import hashlib
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import uuid4

from app.services.ingestion.structure_extractor import ExtractedSection


@dataclass
class DocumentChunk:
    chunk_id: str
    document_id: str
    section_id: Optional[str]
    document_number: Optional[str]
    document_revision: Optional[str]
    section_title: Optional[str]
    section_number: Optional[str]
    chunk_text: str
    page_number: Optional[int]
    page_start: Optional[int]
    page_end: Optional[int]
    chunk_sequence: int
    character_count: int
    token_count_estimate: int
    extraction_status: str = "success"
    content_hash: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.content_hash and self.chunk_text:
            self.content_hash = hashlib.sha256(self.chunk_text.strip().encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_number": self.document_number,
            "document_revision": self.document_revision,
            "section_title": self.section_title,
            "section_number": self.section_number,
            "chunk_text": self.chunk_text,
            "page_number": self.page_number,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "chunk_sequence": self.chunk_sequence,
            "character_count": self.character_count,
            "token_count_estimate": self.token_count_estimate,
            "extraction_status": self.extraction_status,
            "content_hash": self.content_hash,
            "metadata": self.metadata,
        }


class ChunkingEngine:
    """Structure-aware chunking engine with configurable size and overlap."""

    def __init__(self, max_chunk_chars: int = 1200, overlap_chars: int = 150):
        self.max_chunk_chars = max(300, max_chunk_chars)
        self.overlap_chars = max(0, min(overlap_chars, self.max_chunk_chars // 3))

    def create_chunks(
        self,
        document_id: str,
        document_number: Optional[str],
        document_revision: Optional[str],
        sections: list[ExtractedSection],
    ) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        sequence = 1

        for section in sections:
            header_prefix = ""
            if section.section_title and section.section_title != "Preamble / Header":
                if section.section_number:
                    header_prefix = f"### {section.section_number} {section.section_title}\n\n"
                else:
                    header_prefix = f"### {section.section_title}\n\n"

            content = section.content_text.strip()
            if not content:
                # If section has no content but has a title, create a brief heading chunk
                if header_prefix:
                    text = header_prefix.strip()
                    chunk = self._make_chunk(
                        chunk_id=f"CHK-{uuid4().hex[:8].upper()}",
                        document_id=document_id,
                        section_id=section.section_id,
                        document_number=document_number,
                        document_revision=document_revision,
                        section_title=section.section_title,
                        section_number=section.section_number,
                        chunk_text=text,
                        page_start=section.page_start,
                        page_end=section.page_end,
                        sequence=sequence,
                    )
                    chunks.append(chunk)
                    sequence += 1
                continue

            # Full section text with header prefix
            full_section_text = f"{header_prefix}{content}"

            if len(full_section_text) <= self.max_chunk_chars:
                chunk = self._make_chunk(
                    chunk_id=f"CHK-{uuid4().hex[:8].upper()}",
                    document_id=document_id,
                    section_id=section.section_id,
                    document_number=document_number,
                    document_revision=document_revision,
                    section_title=section.section_title,
                    section_number=section.section_number,
                    chunk_text=full_section_text,
                    page_start=section.page_start,
                    page_end=section.page_end,
                    sequence=sequence,
                )
                chunks.append(chunk)
                sequence += 1
            else:
                # Split section text into structure-preserving subchunks
                sub_texts = self._split_text(full_section_text, header_prefix)
                for sub_text in sub_texts:
                    chunk = self._make_chunk(
                        chunk_id=f"CHK-{uuid4().hex[:8].upper()}",
                        document_id=document_id,
                        section_id=section.section_id,
                        document_number=document_number,
                        document_revision=document_revision,
                        section_title=section.section_title,
                        section_number=section.section_number,
                        chunk_text=sub_text,
                        page_start=section.page_start,
                        page_end=section.page_end,
                        sequence=sequence,
                    )
                    chunks.append(chunk)
                    sequence += 1

        return chunks

    def _split_text(self, text: str, header_prefix: str) -> list[str]:
        # Split on double newlines (paragraphs)
        paras = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks: list[str] = []
        current_parts: list[str] = []
        current_len = 0

        for p in paras:
            p_len = len(p)
            if current_parts and (current_len + p_len + 2 > self.max_chunk_chars):
                joined = "\n\n".join(current_parts)
                chunks.append(joined)

                # Overlap: keep the last paragraph if small enough, or slice end of text
                if self.overlap_chars > 0 and len(current_parts[-1]) <= self.overlap_chars:
                    current_parts = [current_parts[-1], p]
                    current_len = len(current_parts[0]) + p_len + 2
                else:
                    current_parts = [p]
                    current_len = p_len
            else:
                current_parts.append(p)
                current_len += p_len + 2

        if current_parts:
            chunks.append("\n\n".join(current_parts))

        # If any single paragraph was larger than max_chunk_chars, split on sentence boundaries
        final_chunks: list[str] = []
        for ch in chunks:
            if len(ch) > self.max_chunk_chars * 1.3:
                sentences = ch.split(". ")
                sub_parts = []
                sub_len = 0
                for s in sentences:
                    s_str = s.strip()
                    if not s_str:
                        continue
                    if sub_parts and (sub_len + len(s_str) + 2 > self.max_chunk_chars):
                        final_chunks.append(". ".join(sub_parts) + ".")
                        sub_parts = [s_str]
                        sub_len = len(s_str)
                    else:
                        sub_parts.append(s_str)
                        sub_len += len(s_str) + 2
                if sub_parts:
                    final_chunks.append(". ".join(sub_parts))
            else:
                final_chunks.append(ch)

        return final_chunks

    def _make_chunk(
        self,
        chunk_id: str,
        document_id: str,
        section_id: Optional[str],
        document_number: Optional[str],
        document_revision: Optional[str],
        section_title: Optional[str],
        section_number: Optional[str],
        chunk_text: str,
        page_start: Optional[int],
        page_end: Optional[int],
        sequence: int,
    ) -> DocumentChunk:
        char_count = len(chunk_text)
        token_estimate = max(1, char_count // 4)

        metadata = {
            "document_id": document_id,
            "document_number": document_number,
            "revision": document_revision,
            "section_id": section_id,
            "section_title": section_title,
            "section_number": section_number,
            "page_start": page_start,
            "page_end": page_end,
            "sequence": sequence,
        }

        return DocumentChunk(
            chunk_id=chunk_id,
            document_id=document_id,
            section_id=section_id,
            document_number=document_number,
            document_revision=document_revision,
            section_title=section_title,
            section_number=section_number,
            chunk_text=chunk_text,
            page_number=page_start,
            page_start=page_start,
            page_end=page_end,
            chunk_sequence=sequence,
            character_count=char_count,
            token_count_estimate=token_estimate,
            extraction_status="success",
            metadata=metadata,
        )
