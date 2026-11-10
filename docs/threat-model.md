# Threat model and security backlog

## Assets

- Company QMS data and draft/released documents.
- Uploaded evidence and its metadata.
- Provider API keys and prompts sent outside the application.
- Revision history, review decisions, approvals and audit events.
- Organization membership, roles and document access boundaries.

## Main threats

| Threat | MVP behavior | Required production mitigation |
|---|---|---|
| Client forges user/role headers | Development mode accepts demo headers | Replace with OIDC/SSO, verified claims and server-side RBAC; disable development auth only after identity integration |
| Cross-organization data access | Queries are scoped to `X-Organization-Id` value | Derive organization from trusted identity claims; test all endpoints for IDOR and tenant bypass |
| Malicious evidence file | Extension allow-list and max size only | MIME/signature validation, antivirus/sandbox scanning, storage isolation and download policy |
| Prompt injection in evidence | Evidence contents are not extracted or sent today | Treat extracted text as untrusted; isolate instructions, use tool restrictions, verify citations, and retain human review |
| External provider data exposure | Only user inputs + evidence metadata sent in generation prompt | Minimize/redact fields, configure retention/data region/terms, use server-side allow-lists and outbound logging |
| Unsupported AI claims | Output schema and section/reference validation | Add semantic checks, source verification, eval datasets and qualified reviewers |
| Approval spoofing | Development roles are spoofable | Strong identity, least privilege, MFA, separation of duties and authorization tests |
| Audit record alteration | Audit rows in same database | Restrict writes, immutable/append-only export, integrity monitoring and tested retention |
| Database loss or corruption | Local SQLite by default | PostgreSQL, encrypted backups, restore tests, monitoring and migration procedures |
| Leaked secrets | `.env.example` contains blank keys | Secret manager, rotation, repository scanning and never build secrets into frontend |

## Deployment rule

Do not expose this MVP to real customer or regulated quality data. The role selector and `X-Actor-*` headers are for local development only. Setting `DEV_AUTH_ENABLED=false` intentionally fails closed until the application is integrated with a real trusted identity provider.
