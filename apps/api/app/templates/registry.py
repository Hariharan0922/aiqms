"""Configurable starter templates. Requirement codes are internal placeholders, not ISO clause numbers."""
from copy import deepcopy

TEMPLATES = [
    {
        "id": "sop", "name": "Standard Operating Procedure", "category": "Controlled documentation",
        "description": "Define a repeatable, controlled process with clear ownership, steps and records.", "version": "1.0.0",
        "requirements": ["QMS-DOC-CONTROL", "QMS-RECORDS", "QMS-RESPONSIBILITY"],
        "sections": ["purpose", "scope", "responsibilities", "reference", "procedure", "records", "revision_history"],
        "fields": [
            {"key":"organization_name","label":"Organization name","type":"text","required":True,"help":"Use the legal or approved organization name."},
            {"key":"process_owner","label":"Process owner / role","type":"text","required":True,"help":"Identify the accountable role, not an invented person."},
            {"key":"purpose","label":"Purpose","type":"textarea","required":True,"min_length":20,"help":"What outcome should this procedure control?"},
            {"key":"scope","label":"Scope and exclusions","type":"textarea","required":True,"min_length":20,"help":"Identify activities, locations, products and justified exclusions."},
            {"key":"procedure_steps","label":"Procedure steps","type":"textarea","required":True,"min_length":30,"help":"Describe the actual sequence of activities."},
            {"key":"records","label":"Records and forms retained","type":"textarea","required":True,"min_length":10,"help":"List actual records/forms and controlled storage locations when known."},
            {"key":"reviewer_role","label":"Reviewing role","type":"text","required":True},
            {"key":"approver_role","label":"Approving role","type":"text","required":True}
        ]
    },
    {
        "id": "quality-manual", "name": "Quality Manual", "category": "QMS foundation",
        "description": "Describe QMS scope, processes, interactions and organizational responsibilities.", "version": "1.0.0",
        "requirements": ["QMS-SCOPE", "QMS-PROCESS-INTERACTION", "QMS-RESPONSIBILITY", "QMS-DOC-CONTROL"],
        "sections": ["organization", "qms_scope", "exclusions_and_applicability", "process_interactions", "responsibilities", "document_control"],
        "fields": [
            {"key":"organization_name","label":"Organization name","type":"text","required":True},
            {"key":"device_and_services","label":"Devices and services","type":"textarea","required":True,"min_length":20},
            {"key":"sites_and_locations","label":"Sites and locations in scope","type":"textarea","required":True,"min_length":5},
            {"key":"qms_scope","label":"Proposed QMS scope","type":"textarea","required":True,"min_length":30},
            {"key":"activities","label":"Core processes and interactions","type":"textarea","required":True,"min_length":30},
            {"key":"applicability_decisions","label":"Proposed non-applicability decisions and rationale","type":"textarea","required":True,"min_length":10},
            {"key":"management_representative","label":"QMS coordination role","type":"text","required":True},
            {"key":"document_control_owner","label":"Document control role","type":"text","required":True}
        ]
    },
    {
        "id": "risk-management", "name": "Risk Management Procedure", "category": "Risk management",
        "description": "Define how product or process risks are identified, evaluated, controlled and reviewed.", "version": "1.0.0",
        "requirements": ["RISK-METHOD", "RISK-ACCEPTABILITY", "RISK-CONTROLS", "RISK-REVIEW"],
        "sections": ["purpose_and_scope", "roles", "methodology", "risk_acceptability", "controls_and_residual_risk", "review_and_records"],
        "fields": [
            {"key":"organization_name","label":"Organization name","type":"text","required":True},
            {"key":"product_or_process","label":"Product, device or process","type":"textarea","required":True,"min_length":10},
            {"key":"risk_method","label":"Risk analysis method","type":"textarea","required":True,"min_length":20},
            {"key":"acceptability_criteria","label":"Approved risk acceptability criteria","type":"textarea","required":True,"min_length":20},
            {"key":"risk_controls","label":"Risk control options and verification approach","type":"textarea","required":True,"min_length":30},
            {"key":"residual_risk","label":"Residual-risk evaluation and escalation","type":"textarea","required":True,"min_length":20},
            {"key":"review_frequency","label":"Risk review trigger or frequency","type":"text","required":True},
            {"key":"risk_owner","label":"Risk management owner","type":"text","required":True}
        ]
    },
    {
        "id": "capa", "name": "Corrective and Preventive Action (CAPA)", "category": "Monitoring and improvement",
        "description": "Document a process for investigating nonconformities and evaluating corrective actions.", "version": "1.0.0",
        "requirements": ["CAPA-INTAKE", "CAPA-ROOT-CAUSE", "CAPA-EFFECTIVENESS", "CAPA-RECORDS"],
        "sections": ["intake_and_containment", "risk_and_impact", "investigation", "action_plan", "implementation", "effectiveness_and_closure"],
        "fields": [
            {"key":"organization_name","label":"Organization name","type":"text","required":True},
            {"key":"capa_scope","label":"Types of issue covered","type":"textarea","required":True,"min_length":20},
            {"key":"containment_process","label":"Containment and impact assessment","type":"textarea","required":True,"min_length":20},
            {"key":"root_cause_method","label":"Root cause investigation method","type":"textarea","required":True,"min_length":20},
            {"key":"action_approval","label":"Action plan review and approval roles","type":"text","required":True},
            {"key":"effectiveness_check","label":"Effectiveness verification criteria","type":"textarea","required":True,"min_length":20},
            {"key":"escalation","label":"Escalation criteria","type":"textarea","required":True,"min_length":10},
            {"key":"record_owner","label":"CAPA record owner","type":"text","required":True}
        ]
    },
    {
        "id": "internal-audit", "name": "Internal Audit Procedure", "category": "Monitoring and improvement",
        "description": "Plan, conduct, document and follow up internal audits using defined criteria.", "version": "1.0.0",
        "requirements": ["AUDIT-PROGRAM", "AUDIT-INDEPENDENCE", "AUDIT-REPORTING", "AUDIT-FOLLOWUP"],
        "sections": ["program", "auditor_competence", "planning", "conduct", "reporting", "followup"],
        "fields": [
            {"key":"organization_name","label":"Organization name","type":"text","required":True},
            {"key":"audit_program_method","label":"Audit program and risk-based priorities","type":"textarea","required":True,"min_length":25},
            {"key":"audit_criteria","label":"Audit criteria and scope definition","type":"textarea","required":True,"min_length":15},
            {"key":"auditor_competence","label":"Auditor competence requirements","type":"textarea","required":True,"min_length":15},
            {"key":"independence","label":"Impartiality and independence controls","type":"textarea","required":True,"min_length":15},
            {"key":"report_and_followup","label":"Reporting, corrective action and follow-up","type":"textarea","required":True,"min_length":25},
            {"key":"program_owner","label":"Audit program owner","type":"text","required":True}
        ]
    },
    {
        "id": "supplier-evaluation", "name": "Supplier Evaluation Procedure", "category": "Operational control",
        "description": "Define supplier selection, evaluation, monitoring and re-evaluation controls.", "version": "1.0.0",
        "requirements": ["SUPPLIER-SELECTION", "SUPPLIER-MONITORING", "SUPPLIER-RECORDS"],
        "sections": ["classification", "selection", "evaluation", "monitoring", "re-evaluation", "records"],
        "fields": [
            {"key":"organization_name","label":"Organization name","type":"text","required":True},
            {"key":"supplier_categories","label":"Supplier and outsourced-process categories","type":"textarea","required":True,"min_length":15},
            {"key":"risk_criteria","label":"Supplier risk and criticality criteria","type":"textarea","required":True,"min_length":20},
            {"key":"selection_criteria","label":"Initial qualification and selection criteria","type":"textarea","required":True,"min_length":20},
            {"key":"monitoring_method","label":"Performance monitoring and escalation","type":"textarea","required":True,"min_length":20},
            {"key":"reevaluation","label":"Re-evaluation triggers and frequency","type":"textarea","required":True,"min_length":15},
            {"key":"supplier_quality_owner","label":"Supplier quality owner","type":"text","required":True}
        ]
    },
    {
        "id": "design-validation", "name": "Design Verification and Validation Plan", "category": "Product realization",
        "description": "Plan design verification and validation activities with criteria and recorded results.", "version": "1.0.0",
        "requirements": ["DESIGN-INPUTS", "DESIGN-VERIFICATION", "DESIGN-VALIDATION", "DESIGN-RECORDS"],
        "sections": ["purpose_and_scope", "design_inputs", "verification_plan", "validation_plan", "acceptance_criteria", "records_and_approvals"],
        "fields": [
            {"key":"organization_name","label":"Organization name","type":"text","required":True},
            {"key":"device_description","label":"Device and intended use","type":"textarea","required":True,"min_length":20},
            {"key":"design_inputs","label":"Design inputs and applicable requirements","type":"textarea","required":True,"min_length":20},
            {"key":"verification_methods","label":"Verification methods and acceptance criteria","type":"textarea","required":True,"min_length":25},
            {"key":"validation_methods","label":"Validation methods and representative users/use conditions","type":"textarea","required":True,"min_length":25},
            {"key":"sample_rationale","label":"Sample size and test coverage rationale","type":"textarea","required":True,"min_length":15},
            {"key":"design_owner","label":"Design owner","type":"text","required":True}
        ]
    },
    {
        "id": "complaint-handling", "name": "Complaint Handling Procedure", "category": "Monitoring and improvement",
        "description": "Describe complaint intake, evaluation, investigation, escalation and closure.", "version": "1.0.0",
        "requirements": ["COMPLAINT-INTAKE", "COMPLAINT-EVALUATION", "COMPLAINT-ESCALATION", "COMPLAINT-RECORDS"],
        "sections": ["intake", "recording", "evaluation", "investigation", "escalation", "closure_and_trending"],
        "fields": [
            {"key":"organization_name","label":"Organization name","type":"text","required":True},
            {"key":"intake_channels","label":"Complaint intake channels","type":"textarea","required":True,"min_length":10},
            {"key":"triage_criteria","label":"Triage, risk and reportability assessment","type":"textarea","required":True,"min_length":25},
            {"key":"investigation_process","label":"Investigation and decision process","type":"textarea","required":True,"min_length":25},
            {"key":"escalation_rules","label":"Escalation and regulatory assessment route","type":"textarea","required":True,"min_length":20},
            {"key":"closure_criteria","label":"Closure and trend review criteria","type":"textarea","required":True,"min_length":15},
            {"key":"complaint_owner","label":"Complaint process owner","type":"text","required":True}
        ]
    },
    {
        "id": "training-procedure", "name": "Training and Competency Procedure", "category": "Supporting processes",
        "description": "Define role competence, training needs, effectiveness checks and retained records.", "version": "1.0.0",
        "requirements": ["TRAINING-NEEDS", "TRAINING-EFFECTIVENESS", "TRAINING-RECORDS"],
        "sections": ["competence_requirements", "training_needs", "delivery", "effectiveness", "records"],
        "fields": [
            {"key":"organization_name","label":"Organization name","type":"text","required":True},
            {"key":"competency_method","label":"Role competence and qualification method","type":"textarea","required":True,"min_length":20},
            {"key":"training_triggers","label":"Training needs and change triggers","type":"textarea","required":True,"min_length":15},
            {"key":"effectiveness_method","label":"Training effectiveness evaluation","type":"textarea","required":True,"min_length":20},
            {"key":"requalification","label":"Refresher or requalification criteria","type":"textarea","required":True,"min_length":10},
            {"key":"training_records","label":"Training records and record owner","type":"textarea","required":True,"min_length":15},
            {"key":"training_owner","label":"Training process owner","type":"text","required":True}
        ]
    },
    {
        "id": "change-control", "name": "Change Control Procedure", "category": "Controlled documentation",
        "description": "Assess, approve, implement and verify changes affecting QMS processes or products.", "version": "1.0.0",
        "requirements": ["CHANGE-INTAKE", "CHANGE-IMPACT", "CHANGE-APPROVAL", "CHANGE-VERIFICATION"],
        "sections": ["change_request", "impact_assessment", "risk_review", "approval", "implementation", "verification_and_records"],
        "fields": [
            {"key":"organization_name","label":"Organization name","type":"text","required":True},
            {"key":"change_categories","label":"Change categories and change initiation","type":"textarea","required":True,"min_length":15},
            {"key":"impact_method","label":"Quality, regulatory and customer impact assessment","type":"textarea","required":True,"min_length":25},
            {"key":"risk_review","label":"Risk review and required testing criteria","type":"textarea","required":True,"min_length":20},
            {"key":"approval_matrix","label":"Required approvers by change type","type":"textarea","required":True,"min_length":15},
            {"key":"implementation_check","label":"Implementation verification and effectiveness check","type":"textarea","required":True,"min_length":20},
            {"key":"change_owner","label":"Change control owner","type":"text","required":True}
        ]
    }
]

REQUIREMENTS = {
    code: {
        "code": code,
        "title": code.replace("-", " ").title(),
        "source_name": "ISO 13485 requirement mapping (internal reference)",
        "source_edition": "ISO 13485:2016 — verify applicable edition/amendments",
        "source_reference": "To be mapped against licensed standard text",
        "summary": "Internal traceability placeholder. Verify this mapping against the licensed standard, applicable regulations and the organization's QMS scope before relying on it.",
        "verification_status": "requires_verification",
    }
    for code in sorted({r for template in TEMPLATES for r in template["requirements"]})
}


def get_template(template_id: str):
    for template in TEMPLATES:
        if template["id"] == template_id:
            return deepcopy(template)
    return None


def list_templates():
    return deepcopy(TEMPLATES)


def add_custom_template(data: dict) -> dict:
    tid = data.get("id") or data.get("name", "custom").lower().replace(" ", "-")
    data["id"] = tid
    data.setdefault("version", "1.0.0")
    data.setdefault("category", "Custom templates")
    data.setdefault("sections", [f["key"] for f in data.get("fields", [])] if not data.get("sections") else data["sections"])
    data.setdefault("requirements", [])
    for idx, t in enumerate(TEMPLATES):
        if t["id"] == tid:
            TEMPLATES[idx] = data
            return deepcopy(data)
    TEMPLATES.append(data)
    return deepcopy(data)

