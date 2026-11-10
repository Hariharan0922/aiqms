# NVIDIA NIM Hosted API Integration Guide

## Overview

**AiDocMaker** integrates the **NVIDIA NIM (NVIDIA Inference Microservice) Hosted API** as its primary cloud AI inference engine. The previous locally hosted language model architecture (including Ollama, local model binaries, and in-process weights execution) has been retired in favor of high-throughput, low-latency enterprise inference hosted directly on NVIDIA's accelerated computing infrastructure.

---

## API Specifications

| Parameter | Configuration |
| :--- | :--- |
| **Provider** | NVIDIA NIM Hosted API |
| **Base URL** | `https://integrate.api.nvidia.com/v1` |
| **Primary Endpoint** | `POST https://integrate.api.nvidia.com/v1/chat/completions` |
| **Authentication** | Bearer Token (`Authorization: Bearer <NVIDIA_API_KEY>`) |
| **Default Model** | `poolside/laguna-xs-2.1` |
| **Fallback Models** | `meta/llama-3.1-70b-instruct`, `meta/llama-3.1-8b-instruct` |
| **Format** | OpenAI-compatible Chat Completions API |
| **Response Format** | JSON Mode (`response_format: {"type": "json_object"}`) with server-side AST recovery |
| **Timeout** | 120 seconds |
| **Max Retries** | 2 with exponential backoff (1s, 2s) |

---

## Architecture and Data Flow

```
User Input & Dynamic Forms (React)
           │
           ▼
Deterministic Rules Validation (Validation Engine - No AI)
           │
           ▼
Generation Request Builder (NvidiaService)
   - Injects Template Section Definitions
   - Injects Validated Answers & Applicability Rationale
   - Injects ISO 13485:2016 Procedural Directives
   - Enforces JSON Schema Strict Output Contract
           │
           ▼
HTTPS POST /chat/completions (integrate.api.nvidia.com)
           │
           ▼
Server-Side Response Validation & Normalization
   - Reasoning Token Extraction (<think>...</think> stripping)
   - Strict Pydantic Model Validation (GeneratedDocumentContent)
   - Alias & Numerical Key Normalization (e.g., "1" -> "purpose")
           │
           ▼
Template Mapping Service (Structure Preservation)
           │
           ▼
Document Generator (python-docx & ReportLab PDF)
```

---

## Security and Credential Protection

1. **Backend Confidentiality:** The NVIDIA API key (`NVIDIA_API_KEY`) is stored strictly in server-side environment variables (`.env`). It is **never** packaged into client-side code, exposed in Vite frontend builds, or committed to source control.
2. **Access Control:** All API endpoints invoking the NVIDIA NIM service require authenticated role authorization (`X-Actor-Role`).
3. **Data Minimization:** Only organization-specific answers, field names, and ISO requirement references necessary for document drafting are transmitted. Raw binary file uploads and server tokens are kept within private application storage.

---

## Dedicated Backend Service: `NvidiaService`

Location: [`apps/api/app/services/nvidia_service.py`](file:///d:/newproject/AIQMS%20LLM%20PROJECT/apps/api/app/services/nvidia_service.py)

Key methods:
- `is_configured`: Boolean property confirming whether a non-empty `NVIDIA_API_KEY` is active.
- `test_connection()`: Executes a low-overhead token ping to verify endpoint reachability, TLS handshake, and measures round-trip latency in milliseconds.
- `generate_document_content()`: Submits validated template data, compiles system prompts, applies JSON schema constraints, and returns normalized structured sections.
- `regenerate_section_content()`: Takes an individual section ID, surrounding document context, and optional user instructions to regenerate content for a single section in isolation without altering the remainder of the document.
- `_extract_json()`: Fault-tolerant parser that strips markdown code fences (````json ... ````), extracts bracketed JSON, and strips reasoning tags emitted by reasoning-capable models.

---

## Error Handling and Resilience

1. **Rate Limiting (HTTP 429):** Automatically captured and retried using exponential backoff with jitter up to `NVIDIA_MAX_RETRIES`.
2. **Network Timeouts (HTTP 504 / ReadTimeout):** Bounded by `NVIDIA_TIMEOUT=120`. If exceeded, clear error messages are surfaced indicating endpoint unavailability.
3. **Model Deprecation / Unavailable Model (HTTP 404):** The service raises a clear configuration error recommending fallback to compatible hosted models (`meta/llama-3.1-70b-instruct`).
4. **Malformed JSON Payload:** If the model returns markdown commentary or truncated JSON, `_extract_json()` attempts regex-based AST repair; if unrecoverable, an automated bounded retry is performed before raising a 502 Bad Gateway with diagnostic details.

---

## Diagnostics and Health Endpoints

- `GET /api/v1/system/diagnostics`: Returns full platform health, database latency, NVIDIA NIM connection latency, and document rendering test results.
- `POST /api/v1/system/test-nvidia`: Executes live round-trip latency test against `https://integrate.api.nvidia.com/v1`, returning latency in milliseconds, active model ID, and verified sample output.
