# Data dictionary

| Entity/table | Purpose | Important invariants |
|---|---|---|
| `documents` | Stable controlled-document identity | Unique document number, organization scope, current version pointer |
| `document_versions` | Immutable-on-release revision | Unique `(document_id, revision)`; answers/applicability/content snapshot; provider and prompt metadata |
| `validation_runs` | Versioned validation results | Stores ruleset version, result and findings snapshot |
| `requirement_references` | Internal requirement library | Starter mappings explicitly marked `requires_verification`; codes are not clause numbers |
| `traceability_links` | Requirement to version/section association | A link alone never asserts conformity |
| `evidence_files` | Metadata for uploaded evidence | Opaque storage key, SHA-256 checksum, original filename, uploader, scope to a version |
| `review_decisions` | Independent review history | Bound to one version, reviewer and decision |
| `approvals` | Authorized approval history | Bound to one version, approver and decision |
| `audit_events` | Significant lifecycle history | Actor, role, action, target and metadata; production must protect log integrity |

## Important JSON properties

- `document_versions.answers`: form-field key -> user-supplied value.
- `document_versions.applicability`: internal requirement code -> `{status, rationale}` where status is `pending`, `applicable`, or `not_applicable`.
- `document_versions.content`: schema-validated generated document JSON.
- `validation_runs.findings`: stable finding code, field path, severity, blocking flag, question and linked requirement ID.
- `traceability_links.evidence_refs`: IDs of available evidence records once linked by a future evidence-mapping UI.

## Production migration notes

The MVP initializes tables with SQLAlchemy `create_all`. For production, adopt Alembic with reviewed migrations, constraints, indexes, backup/restore tests, retention handling and database-specific isolation controls. Do not deploy breaking ORM schema edits without a migration plan.
