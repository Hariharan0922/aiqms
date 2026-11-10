# Architecture and key decisions

## System boundaries

- **Web client:** renders templates, collects user inputs, shows findings, previews drafts and submits workflow decisions.
- **API:** owns lifecycle state, tenant scoping, validation gates, provider invocation, export and audit events.
- **Template registry:** versioned starter schemas. A production template registry should be persisted/published immutably rather than edited in place.
- **Rules engine:** deterministic, side-effect-free field and applicability checks. No AI call is permitted in the generation gate.
- **Prompt service:** compiles validated inputs, internal requirement references, evidence metadata, output schema and generation policy into a versioned request.
- **Provider adapters:** normalize external/local model calls to a shared response contract.
- **Document renderer:** accepts only schema-validated content. Draft exports receive a draft-only notice.
- **Storage:** SQLAlchemy supports SQLite by default and PostgreSQL through `DATABASE_URL`. Local uploads are kept under a private application storage directory.

## Lifecycle

`draft -> validated -> generated -> in_review -> awaiting_approval -> released`

Corrections transition a revision to `changes_requested`; a released revision is immutable and a new revision is created as a separate `DocumentVersion`. The API rejects editing or evidence uploads during review/approval and after release. Every important transition records an audit event.

The current implementation does not include an OIDC integration, malware scanning, OCR, evidence content extraction, database migration tooling, external object storage, background job queue, digital signature service, or verified ISO clause library. Add and validate these before shared/production use.

## Provider contract

`ModelProvider.generate(GenerationRequest) -> GenerationResponse` carries system instructions, a prompt, an output schema, and a token limit. The generation service verifies that returned section IDs exactly match the template's expected set and that requirement/evidence references exist before saving the draft.

The offline provider is deterministic template-based output intended for workflow tests and demos. It is not a language model or quality assessor.

## Data-protection boundary

Only evidence metadata is provided to prompt assembly. Uploaded bytes are not extracted or transmitted to a model in this MVP. When adding extraction or external model context, add file-level classification, consent/configuration, redaction, data minimization, injection-resistant extraction, retention controls and audit records.
