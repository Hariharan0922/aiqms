# AIQMS — Milestone 3.4 Verification Report
## ISO 13485:2016 Knowledge Base Engine

**Status:** Verified & Complete  
**Date:** 2026-10-30  
**Primary Source:** `sample_documents/ISO-13485-2016-EN.pdf`  
**Embedding Model:** Local Ollama `nomic-embed-text` (768 dimensions, `search_document:` / `search_query:`)  
**Vector Database:** ChromaDB (Collection: `aiqms_iso_clauses`)  
**Authoritative Relational Database:** PostgreSQL / SQLite (`iso_clauses` table)  

---

## 1. Executive Summary

Milestone 3.4 establishes an authoritative, structured ISO 13485:2016 Knowledge Base extracted directly from the official PDF standard (`sample_documents/ISO-13485-2016-EN.pdf`). The system extracts the complete clause hierarchy (Clauses 1 through 8, down to 4th-level subclauses), parses normative requirements, isolates explanatory `NOTE` sections, identifies required documented procedures and records, records exact source PDF page boundaries, stores immutable relational records, and indexes all clauses into ChromaDB for high-precision semantic search.

---

## 2. Extraction & Hierarchy Statistics

| Metric | Measured Value | Standard Specification / Notes |
|---|---|---|
| **Total Canonical Clauses Extracted** | **88 clauses** | Complete Clauses 1 to 8 of ISO 13485:2016 |
| **Level 1 (Main Clauses)** | **8 clauses** | Clauses 1, 2, 3, 4, 5, 6, 7, 8 |
| **Level 2 (Subclauses)** | **23 clauses** | e.g. 4.1, 4.2, 5.1–5.6, 6.1–6.4, 7.1–7.6, 8.1–8.5 |
| **Level 3 (Requirements)** | **55 clauses** | e.g. 4.2.1–4.2.5, 5.4.1, 7.3.1–7.3.10, 7.5.1–7.5.11, 8.2.1–8.2.6 |
| **Level 4 (Specific Requirements)**| **2 clauses** | 7.5.9.1 (General) & 7.5.9.2 (Implantable medical devices) |
| **Source PDF Page Range** | **Pages 9 to 35** | Covers complete text from Clause 1 to Clause 8.5.3 |
| **Vectors Indexed in ChromaDB** | **88 embeddings** | Collection: `aiqms_iso_clauses`, 768 dimensions each |
| **Deduplication / Re-sync** | **100% hash-verified** | Re-sync skips unmodified clauses (0 duplicate rows created) |

---

## 3. Normative Text & Explanatory Notes Separation

In ISO standards, paragraphs beginning with `NOTE` are informative and explanatory, not normative requirements. `ISOPdfExtractor` cleanly distinguishes between normative requirements and notes:

- **Clause 7.5.7** (*Particular requirements for validation of processes for sterilization and sterile barrier systems*):
  - **Normative Text:** *"The organization shall document procedures (see 4.2.4) for the validation of processes for sterilization and sterile barrier systems. Processes for sterilization and sterile barrier systems shall be validated prior to implementation..."*
  - **Explanatory Notes:** `NOTE Further information can be found in ISO 11607-1 and ISO 11607-2.`
- **Clause 7.6** (*Control of monitoring and measuring equipment*):
  - **Explanatory Notes:** `NOTE Further information can be found in ISO 10012.`
- **Clause 6.4.1** (*Work environment*):
  - **Explanatory Notes:** `NOTE Further information can be found in ISO 14644 and ISO 14698.`

---

## 4. Empirical Retrieval & Semantic Search Benchmarks

Natural language queries evaluated against the ChromaDB `aiqms_iso_clauses` vector collection and validated against PostgreSQL authoritative records:

| Query | Expected Clause | Top-1 Retrieved Clause | Title | Cosine Dist | Similarity Score | Status |
|---|---|---|---|---|---|---|
| *"sterile barrier validation process"* | 7.5.7 | **7.5.7** | Particular requirements for validation of processes for sterilization and sterile barrier systems | 0.3435 | **82.83%** | **MATCH** |
| *"medical device file specifications and manufacturing procedures"* | 4.2.3 | **4.2.3** | Medical device file | 0.3771 | **81.15%** | **MATCH** |
| *"management review inputs and outputs"* | 5.6.2 / 5.6.3 | **5.6.2** | Review input | 0.4012 | **79.94%** | **MATCH** |
| *"control of nonconforming product before delivery"* | 8.3.2 | **8.3.2** | Actions in response to nonconforming product detected before delivery | 0.3850 | **80.75%** | **MATCH** |
| *"software and process validation requirements"* | 7.5.6 | **7.5.6** | Validation of processes for production and service provision | 0.4120 | **79.40%** | **MATCH** |

---

## 5. API Endpoints Verified

1. `GET /api/v1/compliance/iso13485/clauses` — Returns all 88 clauses with filters for `category`, `parent`, `level`, and `q` (keyword).
2. `GET /api/v1/compliance/iso13485/clauses/{clause_number}` — Returns single clause with parent object, children subclauses, normative text, notes, and procedure/record flags.
3. `GET /api/v1/compliance/iso13485/hierarchy` — Returns complete recursive tree of clauses from Level 1 to Level 4.
4. `POST /api/v1/compliance/iso13485/sync` — Synchronizes PDF extraction to DB and ChromaDB with deduplication (`force_reindex` flag).
5. `POST /api/v1/compliance/iso13485/search` — Semantic search over ISO clauses using Ollama `nomic-embed-text` and ChromaDB.

---

## 6. Test Suite Results

`apps/api/tests/test_milestone_3_4_iso_kb.py` executed via pytest:
```
apps/api/tests/test_milestone_3_4_iso_kb.py::TestISOPdfExtraction::test_extract_all_canonical_clauses PASSED [  7%]
apps/api/tests/test_milestone_3_4_iso_kb.py::TestISOPdfExtraction::test_clause_hierarchy_and_levels PASSED [ 14%]
apps/api/tests/test_milestone_3_4_iso_kb.py::TestISOPdfExtraction::test_page_references_preservation PASSED [ 21%]
apps/api/tests/test_milestone_3_4_iso_kb.py::TestISOPdfExtraction::test_explanatory_notes_separation PASSED [ 28%]
apps/api/tests/test_milestone_3_4_iso_kb.py::TestISOPdfExtraction::test_procedure_and_record_flags PASSED [ 35%]
apps/api/tests/test_milestone_3_4_iso_kb.py::TestISOKnowledgeBaseService::test_sync_and_duplicate_prevention PASSED [ 42%]
apps/api/tests/test_milestone_3_4_iso_kb.py::TestISOKnowledgeBaseService::test_single_clause_detail_with_relationships PASSED [ 50%]
apps/api/tests/test_milestone_3_4_iso_kb.py::TestISOKnowledgeBaseService::test_hierarchy_tree_structure PASSED [ 57%]
apps/api/tests/test_milestone_3_4_iso_kb.py::TestISOKnowledgeBaseService::test_semantic_clause_search PASSED [ 64%]
apps/api/tests/test_milestone_3_4_iso_kb.py::TestISOKnowledgeAPI::test_get_iso_clauses_list PASSED [ 71%]
apps/api/tests/test_milestone_3_4_iso_kb.py::TestISOKnowledgeAPI::test_get_iso_clauses_filtered_by_category PASSED [ 78%]
apps/api/tests/test_milestone_3_4_iso_kb.py::TestISOKnowledgeAPI::test_get_iso_clause_by_number_endpoint PASSED [ 85%]
apps/api/tests/test_milestone_3_4_iso_kb.py::TestISOKnowledgeAPI::test_get_iso_hierarchy_tree_endpoint PASSED [ 92%]
apps/api/tests/test_milestone_3_4_iso_kb.py::TestISOKnowledgeAPI::test_search_iso_clauses_api PASSED [100%]

============================= 14 passed in 55.96s =============================
```

---

## 7. Next Steps

With Milestone 3.4 verified and operational, the system now proceeds to **Milestones 3.5 & 3.6**: building the deterministic ISO 13485 clause-to-QMS-document traceability system and rules-based evidence validation engine.
