# Traceability matrix starter

| Lifecycle requirement | Implementation location | Current evidence / status | Remaining production work |
|---|---|---|---|
| Required input completeness | `app/rules/engine.py` | Unit and API tests cover missing fields | Expand schema/rule tests and risk-based validation coverage |
| Applicability recorded | `app/rules/engine.py`; document `applicability` JSON | Pending applicability blocks generation; N/A rationale required | Formal applicability governance and authorized disposition |
| Template identity | `documents.template_id`, `template_version` | Version field saved with document | Publish immutable DB-backed template versions |
| Validation trace | `validation_runs` | Stores ruleset version, findings and result | Retention, reports, test evidence and controlled rule changes |
| Requirement source trace | `requirement_references`, `traceability_links` | Internal placeholder codes; visibly unverified | Map each requirement against licensed applicable source material |
| Output section trace | `traceability_links.section_id` | Generated section references are linked | Reviewer verification of content sufficiency and evidence |
| Evidence provenance | `evidence_files` | Filename, uploader, timestamp, checksum stored | Malware scanning, content inspection, object storage, evidence-to-requirement mapping UI |
| Prompt provenance | `prompt_version`, `input_hash`, provider/model ID | Stored at generation | Keep versioned prompt snapshots when justified and governed |
| Independent review | `review_decisions` | Author is barred from reviewing their own revision | Role provisioning, formal review criteria and test evidence |
| Approval/release | `approvals`, `document_versions.status` | Author cannot approve own revision; released revision locked | Formal authorization matrix, signature evaluation and controlled distribution |
| Audit history | `audit_events` | Lifecycle transitions and key events recorded | Tamper-evident/immutable logs, retention and monitoring |
| Document output | `app/exporting/render.py` | DOCX/PDF tests verify output formats | Template styling, metadata/numbering rules, rendering regression suite |

This matrix records what the starter application implements; it is not a certification checklist or evidence of ISO conformity.
