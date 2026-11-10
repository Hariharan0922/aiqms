# Testing Guide – AiDocMaker Automated Verification

This guide outlines the automated test architecture, test suites, and instructions for running and extending tests for **AiDocMaker**.

---

## 1. Test Architecture Overview

The automated test suite contains **89 unit and integration tests** verifying all layers of the refactored architecture:

| Test File | Tests | Focus Area |
| :--- | :--- | :--- |
| `test_nvidia_service.py` | 6 | Mocked & live NVIDIA NIM calls, connection check, latency, JSON extraction, single-section regeneration |
| `test_nvidia_provider.py` | 4 | Adapter contract compatibility with `ModelProvider` interface |
| `test_template_mapping_service.py` | 3 | Section ordering preservation, missing section fallbacks, in-place section updates |
| `test_document_generator.py` | 2 | Genuine DOCX (`PK\x03\x04` zip) and PDF (`%PDF-1.4`) rendering engine tests |
| `test_diagnostics.py` | 4 | Health diagnostics, live NVIDIA NIM connection test, custom template builder, section patch |
| `test_enhancement_service.py` | 4 | ISO 13485 procedural content enhancement from raw topic summaries |
| `test_workflow.py` | 5 | End-to-end document creation, deterministic validation, review queue, and approval gates |
| `test_ingestion.py` | 27 | Document parsing, text chunking, and metadata extraction |
| `test_milestone_3_4_iso_kb.py` | 14 | ISO 13485 clause hierarchy, PDF extraction, and semantic search |
| `test_milestone_3_5_3_6_traceability.py` | 11 | Traceability matrix and clause verification status |
| `test_vectors_and_compliance.py` | 9 | End-to-end vector indexing and compliance audit |
| **Total** | **89** | **100% Passed (38.88s)** |

---

## 2. Running Automated Tests

### 2.1. Run Full Suite

From the project root:
```bash
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests
```

### 2.2. Run Core Refactored Suites Only

To run the core NVIDIA NIM, template mapping, document rendering, and diagnostics suites:
```bash
apps/api/.venv/Scripts/python.exe -m pytest \
  apps/api/tests/test_diagnostics.py \
  apps/api/tests/test_document_generator.py \
  apps/api/tests/test_template_mapping_service.py \
  apps/api/tests/test_nvidia_service.py \
  apps/api/tests/test_nvidia_provider.py \
  apps/api/tests/test_enhancement_service.py \
  apps/api/tests/test_workflow.py
```

### 2.3. Run with Verbose Output and Timing
```bash
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests -v --durations=10
```

---

## 3. Frontend Build Verification

To verify that all JSX, CSS, and component integrations compile cleanly without TypeScript/Babel errors:

```bash
npm --prefix apps/web run build
```
Expected output:
```
✓ 1581 modules transformed.
dist/index.html                   0.62 kB
dist/assets/index.css            60.50 kB
dist/assets/index.js            315.56 kB
✓ built in 1.44s
```

---

## 4. Mocking Strategy

- **NVIDIA NIM API:** Tests in `test_nvidia_service.py` use `unittest.mock.patch` over `httpx.Client.post` to simulate HTTP 200, HTTP 429 (rate limits), and HTTP 504 (timeouts) without incurring live API token consumption or network jitter during CI/CD.
- **Offline / Isolated Tests:** The deterministic `Offline` provider remains active in unit tests to guarantee reproducibility without external network requirements.
