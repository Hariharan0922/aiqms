from enum import StrEnum
from pydantic import BaseModel, Field

class Severity(StrEnum):
    BLOCKER = "blocker"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class ValidationFinding(BaseModel):
    code: str
    field_path: str
    severity: Severity
    message: str
    question: str | None = None
    requirement_id: str | None = None
    blocks_generation: bool = False
    resolved: bool = False

class ValidationResult(BaseModel):
    document_version_id: str
    ruleset_version: str
    passed: bool
    can_generate: bool
    findings: list[ValidationFinding] = Field(default_factory=list)
