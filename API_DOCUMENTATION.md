# REST API Documentation – AiDocMaker

Base URL: `http://localhost:8000/api/v1`  
Interactive OpenAPI Swagger Docs: `http://localhost:8000/docs`

---

## 1. Authentication and Headers

In the local development environment, role simulation and tenant scoping are passed via request headers:

| Header Name | Type | Example | Description |
| :--- | :--- | :--- | :--- |
| `X-Actor-Email` | String | `demo.author@example.local` | Email of the acting user |
| `X-Actor-Role` | String | `author`, `reviewer`, `approver`, `admin` | Simulated role for permission verification |
| `X-Organization-Id` | String | `demo-org` | Tenant boundary identifier |

---

## 2. Template Endpoints

### 2.1. List All Templates
- **Method:** `GET`
- **Path:** `/templates`
- **Description:** Returns all starter and custom registered document templates.
- **Response (200 OK):**
```json
[
  {
    "id": "sop",
    "name": "Standard Operating Procedure",
    "document_type": "SOP",
    "category": "Quality Assurance",
    "version": "1.0",
    "description": "Standard operating procedure template",
    "sections": [
      { "section_id": "purpose", "title": "Purpose", "order": 1, "required": true },
      { "section_id": "scope", "title": "Scope", "order": 2, "required": true },
      { "section_id": "procedure", "title": "Procedure", "order": 3, "required": true }
    ],
    "fields": [
      { "key": "department", "label": "Department", "type": "text", "required": true }
    ]
  }
]
```

### 2.2. Create Custom Template
- **Method:** `POST`
- **Path:** `/templates`
- **Description:** Dynamically registers a custom template with user-defined sections and input fields.
- **Request Body:**
```json
{
  "name": "Cleanroom Environmental Monitoring Procedure",
  "document_type": "SOP-CR",
  "category": "Environmental Control",
  "description": "Procedure for viable and particulate air monitoring in cleanrooms",
  "sections": [
    { "section_id": "purpose", "title": "Purpose", "order": 1, "required": true },
    { "section_id": "scope", "title": "Scope", "order": 2, "required": true },
    { "section_id": "monitoring_protocol", "title": "Monitoring Protocol", "order": 3, "required": true }
  ],
  "fields": [
    { "key": "cleanroom_class", "label": "Cleanroom ISO Classification", "type": "text", "required": true },
    { "key": "sample_frequency", "label": "Sampling Frequency", "type": "select", "options": ["Daily", "Weekly", "Monthly"], "required": true }
  ]
}
```
- **Response (201 Created):** Returns the registered template object.

---

## 3. Document Lifecycle Endpoints

### 3.1. Create Blank Document
- **Method:** `POST`
- **Path:** `/documents`
- **Request Body:**
```json
{
  "template_id": "sop",
  "title": "Cleanroom Gowning and Entry Procedure",
  "answers": {}
}
```

### 3.2. Validate Document Inputs
- **Method:** `POST`
- **Path:** `/documents/{document_id}/validate`
- **Description:** Runs deterministic rules engine checking required fields and applicability rationale. Zero external AI calls.
- **Response (200 OK):**
```json
{
  "can_generate": true,
  "findings": []
}
```

### 3.3. Generate Document via NVIDIA NIM
- **Method:** `POST`
- **Path:** `/documents/{document_id}/generate`
- **Request Body:**
```json
{
  "provider": "nvidia"
}
```
- **Description:** Calls NVIDIA NIM hosted API (`https://integrate.api.nvidia.com/v1/chat/completions`), parses structured JSON response, aligns sections via `TemplateMappingService`, and updates document content.

### 3.4. Edit Section Content In-Place
- **Method:** `PATCH`
- **Path:** `/documents/{document_id}/sections/{section_id}`
- **Request Body:**
```json
{
  "content": "Updated procedure content with specific ISO 14644-1 particulate count criteria."
}
```
- **Response (200 OK):** Returns the updated document with modified revision content.

### 3.5. Regenerate Single Section via NVIDIA NIM
- **Method:** `POST`
- **Path:** `/documents/{document_id}/sections/{section_id}/regenerate`
- **Request Body:**
```json
{
  "instruction": "Expand the procedure with step-by-step verification instructions under ISO 13485:2016 Clause 7.5.",
  "provider": "nvidia"
}
```
- **Response (200 OK):** Returns the document with only the targeted section regenerated and updated.

### 3.6. Export Document (DOCX / PDF)
- **Method:** `GET`
- **Path:** `/documents/{document_id}/export?format={docx|pdf}`
- **Description:** Downloads genuine binary Microsoft Word `.docx` (with zip header) or Adobe `.pdf` (ReportLab formatted).

---

## 4. System Diagnostics & Telemetry

### 4.1. Live System Diagnostics
- **Method:** `GET`
- **Path:** `/system/diagnostics`
- **Description:** Runs automated checks verifying database health, NVIDIA NIM round-trip latency, and document rendering pipelines.
- **Response (200 OK):**
```json
{
  "status": "healthy",
  "timestamp": "2026-10-31T13:40:00Z",
  "checks": {
    "database": {
      "status": "ok",
      "latency_ms": 1.15
    },
    "nvidia_nim": {
      "status": "ok",
      "latency_ms": 380.4,
      "model": "poolside/laguna-xs-2.1",
      "base_url": "https://integrate.api.nvidia.com/v1"
    },
    "document_rendering": {
      "status": "ok",
      "docx": "ok",
      "pdf": "ok"
    }
  }
}
```

### 4.2. Test NVIDIA NIM Connection
- **Method:** `POST`
- **Path:** `/system/test-nvidia`
- **Description:** Executes live token benchmark against NVIDIA NIM.
- **Response (200 OK):**
```json
{
  "status": "ok",
  "latency_ms": 342.1,
  "model": "poolside/laguna-xs-2.1",
  "base_url": "https://integrate.api.nvidia.com/v1",
  "sample_response": "NVIDIA NIM connectivity verified."
}
```

---

## 5. QMS ISO Standard Generation & Knowledge Management API

### 5.1. Generate ISO QMS Document from Summary
- **Method:** `POST`
- **Path:** `/qms/generate-from-summary` (alias: `/documents/generate-from-summary`)
- **Description:** Provide a brief summary or raw operational notes; the cloud AI (NVIDIA NIM) maps the expected ISO 13485:2016 standards, auto-selects or applies the template, validates the quality rules, generates all formal document sections, and outputs ready-to-export DOCX and PDF files.
- **Request Body:**
```json
{
  "summary": "Cleanroom particulate monitoring SOP for ISO Class 7 medical device packaging room, weekly optical particle counts, limits 352,000 at 0.5um, gowning procedure, QA record retention 10 years.",
  "standard": "ISO 13485:2016",
  "template_id": "sop",
  "organization_name": "Apex Medical Technologies",
  "provider": "nvidia",
  "auto_generate_sections": true
}
```
- **Response (201 Created):**
```json
{
  "status": "success",
  "message": "ISO standard QMS document created and generated from summary successfully.",
  "standard": "ISO 13485:2016",
  "document": {
    "id": "ab494874-3cb1-4127-8f42-4df04f28127a",
    "document_number": "QMS-20261103-B7B36766",
    "title": "Standard Operating Procedure for Cleanroom Particulate Monitoring in ISO Class 7 Medical Device Packaging Environment",
    "document_type": "Standard Operating Procedure",
    "template_id": "sop",
    "status": "generated",
    "validation_status": "passed",
    "provider": "nvidia",
    "model_id": "poolside/laguna-xs-2.1"
  },
  "iso_standards_context": {
    "standard": "ISO 13485:2016",
    "relevant_clauses": [
      {
        "clause_number": "6.3",
        "title": "Infrastructure",
        "requires_documented_procedure": true,
        "requires_record": true
      }
    ]
  },
  "generated_content": { ... },
  "export_urls": {
    "docx": "/api/v1/documents/ab494874-3cb1-4127-8f42-4df04f28127a/export?format=docx",
    "pdf": "/api/v1/documents/ab494874-3cb1-4127-8f42-4df04f28127a/export?format=pdf"
  }
}
```

### 5.2. Preview ISO Data from Summary (Stateless)
- **Method:** `POST`
- **Path:** `/qms/preview-iso-data`
- **Description:** Generates structured ISO 13485 quality fields, matched clauses, and regulatory applicability decisions without persisting records to the database.
- **Request Body:**
```json
{
  "summary": "Monitoring of airborne particulates in Class 7 cleanroom packaging suites using laser counters, sterile gowning verification, and archiving batch records for 10 years.",
  "standard": "ISO 13485:2016",
  "provider": "nvidia"
}
```

### 5.3. Add ISO Standard Requirement via API
- **Method:** `POST`
- **Path:** `/requirements`
- **Description:** Add or register custom ISO regulatory requirement mappings in the system.
- **Request Body:**
```json
{
  "code": "ISO13485-6.4.2",
  "title": "Contamination Control in Work Environment",
  "source_name": "ISO 13485:2016",
  "source_edition": "ISO 13485:2016",
  "source_reference": "Clause 6.4.2",
  "summary": "Requirements for the control of contamination with microorganisms or particulate matter.",
  "verification_status": "verified",
  "verification_note": "Verified against ISO 13485 standard text."
}
```

### 5.4. Add ISO Clause to Knowledge Base via API
- **Method:** `POST`
- **Path:** `/compliance/iso13485/clauses`
- **Description:** Add a new clause to the ISO 13485 repository.
- **Request Body:**
```json
{
  "clause_number": "7.5.12",
  "title": "Robotic Surgical Device Assembly",
  "category": "Product realization",
  "parent_clause_number": "7.5",
  "level": 3,
  "clause_text": "The organization shall document procedures and maintain records for automated assembly.",
  "summary_requirements": "Procedures and records for automated assembly.",
  "requires_documented_procedure": true,
  "requires_record": true,
  "standard": "ISO 13485:2016"
}
```
