# AiDocMaker – NVIDIA NIM API-Based Intelligent Document Automation Platform

**AiDocMaker** is an enterprise-grade document automation platform built for quality and compliance documentation (ISO 13485:2016, FDA 21 CFR Part 820, GxP). The platform replaces legacy local model execution and complex local LLM stacks with **NVIDIA's hosted NIM (NVIDIA Inference Microservice) API**, combining deterministic backend rules validation with fast, structured cloud AI generation and authentic DOCX / PDF rendering.

---

## Key Features

- **NVIDIA NIM Hosted Inference:** Enterprise document generation via NVIDIA's OpenAI-compatible endpoint (`https://integrate.api.nvidia.com/v1`), featuring sub-second round-trip latency, automatic retries, and strict schema validation.
- **Deterministic Rules Validation Engine:** Zero-AI mandatory validation gate verifying required fields, string constraints, data types, and ISO requirement applicability decisions before any cloud API call.
- **Template Library & Custom Template Builder:** 10 pre-configured quality templates (SOP, CAPA, Quality Manual, Change Control, etc.) plus a dynamic custom template builder allowing teams to author sections, fields, and validation rules.
- **Section-Level Editing & Single-Section Regeneration:** Edit any section directly in-place or trigger targeted AI regeneration with custom prompt instructions without modifying or regenerating other sections.
- **Authentic Document Rendering Engine:** Generates genuine Microsoft Word (`.docx` with `PK\x03\x04` zip header and styled tables) and Adobe PDF (`.pdf` via ReportLab with `%PDF-1.4` binary header and page numbering).
- **Controlled Lifecycle & Quality Gates:** Strict 6-state lifecycle (`draft` → `validated` → `generated` → `in_review` → `awaiting_approval` → `released`) enforcing independent author, reviewer, and approver identity separation.
- **Live System Diagnostics & Latency Monitoring:** In-app telemetry displaying live database latency, NVIDIA NIM round-trip latency, and document rendering health.

---

## Architecture Overview

```
User Interface (React + Vite)
           │
           ▼
Dynamic Template Selection & Dynamic Form
           │
           ▼
Deterministic Backend Validation (FastAPI)
   [Checks: Required Fields, Data Types, Applicability Decisions]
           │
           ▼
Generation Request Builder (NvidiaService)
   [System instructions, ISO standard requirements, strict schema]
           │
           ▼
NVIDIA NIM Hosted API (POST /v1/chat/completions)
   [Model: poolside/laguna-xs-2.1 or meta/llama-3.1-70b-instruct]
           │
           ▼
Response Parsing, Normalization & Pydantic Validation
           │
           ▼
Template Mapping Engine (Ordering & Formatting Preservation)
           │
           ▼
Document Rendering Engine (python-docx & ReportLab)
           │
           ▼
Document Preview, History, and DOCX/PDF Export
```

---

## Quick Start (Local Development)

### Prerequisites

- **Python:** 3.11+ (Python 3.13 supported)
- **Node.js:** 20+ and npm
- **NVIDIA API Key:** Obtain from [NVIDIA Build](https://build.nvidia.com)

### 1. Backend Setup

```bash
cd apps/api
python -m venv .venv

# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate

pip install -r requirements.txt
```

Configure `apps/api/.env` (or copy from `.env.example`):
```ini
NVIDIA_API_KEY=nvapi-your-key-here
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=poolside/laguna-xs-2.1
NVIDIA_TIMEOUT=120
NVIDIA_MAX_RETRIES=2
```

Start the FastAPI application:
```bash
uvicorn app.main:app --reload --port 8000
```
Swagger UI documentation is available at `http://localhost:8000/docs`.

### 2. Frontend Setup

In a separate terminal:
```bash
cd apps/web
npm install
npm run dev
```
Open your browser at `http://localhost:5173`.

---

## Running the Automated Test Suite

The platform includes 89 automated tests covering diagnostics, rendering, validation, template mapping, and NVIDIA NIM integration:

```bash
# From workspace root using the virtual environment:
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests
```

To build the React production bundle:
```bash
npm --prefix apps/web run build
```

---

## Documentation Index

1. [`ARCHITECTURE.md`](./ARCHITECTURE.md) – Comprehensive system architecture, data models, and workflow specifications.
2. [`NVIDIA_API_INTEGRATION.md`](./NVIDIA_API_INTEGRATION.md) – Hosted API endpoints, authentication, models, retries, and latency optimization.
3. [`API_DOCUMENTATION.md`](./API_DOCUMENTATION.md) – Complete REST API reference, endpoints, and request/response schemas.
4. [`ENVIRONMENT_SETUP.md`](./ENVIRONMENT_SETUP.md) – Step-by-step installation, environment variables, and configuration options.
5. [`TESTING_GUIDE.md`](./TESTING_GUIDE.md) – Test suite structure, running unit/integration/e2e tests, and mock strategies.
6. [`DEPLOYMENT_GUIDE.md`](./DEPLOYMENT_GUIDE.md) – Production deployment, Docker Compose, security checklists, and monitoring.
7. [`MIGRATION_REPORT.md`](./MIGRATION_REPORT.md) – Detailed report on the retirement of legacy local LLMs and migration to NVIDIA NIM.
