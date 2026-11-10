from pydantic import BaseModel, Field
from typing import Any

class CreateDocumentRequest(BaseModel):
    template_id: str
    title: str = Field(min_length=3, max_length=240)
    answers: dict[str, Any] = Field(default_factory=dict)

class UpdateAnswersRequest(BaseModel):
    answers: dict[str, Any] | None = None
    applicability: dict[str, Any] | None = None

class GenerateRequest(BaseModel):
    provider: str = "offline"

class ReviewRequest(BaseModel):
    decision: str
    comments: str = ""

class ApproveRequest(BaseModel):
    decision: str = "approve"
    comments: str = ""

class ResolveFindingsRequest(BaseModel):
    resolutions: dict[str, dict[str, Any]] = Field(default_factory=dict)


class RequirementUpdateRequest(BaseModel):
    source_edition: str = Field(min_length=2, max_length=100)
    source_reference: str = Field(min_length=2, max_length=160)
    summary: str = Field(min_length=10, max_length=4000)
    verification_status: str = "requires_verification"
    verification_note: str = ""

class EnhanceFromSummaryRequest(BaseModel):
    template_id: str
    summary: str = Field(min_length=10, max_length=5000)
    organization_name: str | None = None
    provider: str = "nvidia"
    create_document: bool = False

class EnhanceDocSummaryRequest(BaseModel):
    summary: str = Field(min_length=10, max_length=5000)
    organization_name: str | None = None
    provider: str = "nvidia"


class GenerateFromSummaryRequest(BaseModel):
    summary: str = Field(min_length=10, max_length=10000, description="Short summary, brief notes, or raw description of QMS details")
    standard: str = Field(default="ISO 13485:2016", description="Target quality standard, e.g. ISO 13485:2016, ISO 9001:2015, FDA 21 CFR 820")
    template_id: str | None = Field(default=None, description="Optional template ID. If omitted, matching ISO template is auto-detected")
    organization_name: str | None = Field(default=None, description="Legal or operating organization name")
    provider: str = Field(default="nvidia", description="AI provider: 'nvidia' for cloud NIM API or 'offline' for deterministic rules")
    auto_generate_sections: bool = Field(default=True, description="Whether to also run cloud section generation immediately")


class PreviewIsoDataRequest(BaseModel):
    summary: str = Field(min_length=10, max_length=10000, description="Short summary of QMS details")
    standard: str = Field(default="ISO 13485:2016", description="Target quality standard")
    template_id: str | None = Field(default=None, description="Optional template ID")
    organization_name: str | None = Field(default=None, description="Organization name")
    provider: str = Field(default="nvidia", description="AI provider: 'nvidia' or 'offline'")


class CreateRequirementRequest(BaseModel):
    code: str = Field(min_length=2, max_length=100, description="Unique requirement code, e.g. ISO13485-6.4.2")
    title: str = Field(min_length=2, max_length=240, description="Requirement title")
    source_name: str = Field(default="ISO 13485:2016", max_length=240)
    source_edition: str = Field(default="ISO 13485:2016", max_length=100)
    source_reference: str = Field(min_length=2, max_length=160, description="Clause or reference number")
    summary: str = Field(min_length=10, max_length=4000, description="Normative summary")
    verification_status: str = Field(default="verified", description="verification status")
    verification_note: str = Field(default="Added via API", max_length=1000)


class CreateCustomTemplateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=150)
    category: str = "Custom templates"
    description: str = ""
    sections: list[str] = Field(default_factory=list)
    fields: list[dict[str, Any]] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)


class RegenerateSectionRequest(BaseModel):
    guidance: str = ""
    provider: str = "nvidia"


class UpdateSectionContentRequest(BaseModel):
    title: str | None = None
    content: str
    requirement_refs: list[str] | None = None
    unresolved_items: list[str] | None = None

