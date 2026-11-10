from pydantic import BaseModel, Field

class GeneratedSection(BaseModel):
    section_id: str
    title: str
    content: str
    requirement_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    unresolved_items: list[str] = Field(default_factory=list)

class GeneratedDocument(BaseModel):
    title: str
    document_type: str
    purpose: str
    scope: str
    sections: list[GeneratedSection]
    open_issues: list[str] = Field(default_factory=list)
    review_notes: list[str] = Field(default_factory=list)
