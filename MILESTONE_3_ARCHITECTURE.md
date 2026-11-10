# AIQMS — MILESTONE 3 ARCHITECTURE DESIGN
## Vector Embedding, Semantic Retrieval & ISO 13485 Traceability Validation

**Project:** AIQMS – ISO 13485 AI-Powered Quality Management System  
**Milestone:** 3 – Vector Storage, Semantic Search & AI Traceability Engine  
**Author:** AIQMS Engineering Team (Senior Python Backend Developer, AI Engineer, Software Architect, QA Automation Engineer)  
**Status:** PROPOSED & READY FOR APPROVAL  
**Date:** October 30, 2026  
**Execution Environment:** Windows (x64), Python 3.13.2, FastAPI 0.162, SQLAlchemy 2.1.6, Ollama Local Server (Port 11434)  

---

## 1. EXECUTIVE SUMMARY & LOCAL ENVIRONMENT AUDIT

Milestone 3 builds on the completed foundations of **Milestone 1** (Full-Stack Architecture & QMS Lifecycle) and **Milestone 2** (Document Ingestion & Processing Engine). The objective of Milestone 3 is to establish a 100% offline, air-gapped, verifiable AI intelligence layer:

1. **High-Performance Vector Embeddings:** Transform structured QMS document chunks into dense semantic vectors using the local Ollama `nomic-embed-text` model (768 dimensions).
2. **Embedded Vector Database (ChromaDB):** Store and index document chunk vectors alongside full regulatory provenance metadata using an in-process, zero-cloud ChromaDB persistent instance.
3. **Semantic Retrieval Engine:** Deliver sub-second hybrid semantic and keyword search across standard operating procedures (SOPs), quality manuals, and technical files.
4. **Automated ISO 13485 Traceability Validation:** Compare draft QMS procedures against authoritative ISO 13485:2016 clauses using local LLM reasoning (`qwen3:4b`), pinpointing gaps, missing records, and compliance strengths without hallucinating approvals or mutating source texts.

### Empirical Verification of Local AI Infrastructure (Completed October 30, 2026)

The following live checks were executed directly against the local host environment:

| Component | Target / Host | Status | Details & Metrics |
|---|---|---|---|
| **Ollama Server** | `http://localhost:11434` | **ONLINE** | Daemon active, responding to `/api/tags`, `/api/embed`, `/api/generate` |
| **Embedding Model** | `nomic-embed-text:latest` | **VERIFIED** | Size: 261.6 MB (274 MB on disk), Context: 2,048 tokens, Dim: 768 float32. Live embed latency: 7.39s (cold start) / 1.62s (warmed) |
| **Primary Reasoning Model** | `qwen3:4b` | **VERIFIED** | Size: 2381.6 MB (2.5 GB on disk), Context: 262,144 tokens, Params: 4.0B. Live generation latency: 8.87s |
| **Secondary Reasoning Model**| `qwen3:8b` | **AVAILABLE** | Size: 4983.3 MB (5.2 GB on disk), Context: 40,960 tokens, Params: 8.2B |
| **Python Environment** | `apps/api/.venv` (Python 3.13.2) | **ACTIVE** | `ollama` 0.5.1, `torch` 2.8.0, `numpy` 2.2.4, `scikit-learn` 1.6.1, `fastapi` 0.162, `SQLAlchemy` 2.1.6 |
| **Vector DB (`chromadb`)** | `apps/api/.venv` | **PENDING INSTALL** | Package not yet installed in virtualenv. Planned for Milestone 3 installation or fallback adapter |

---

## 2. EXISTING ARCHITECTURE ASSESSMENT

### 2.1 Milestone 1 & 2 Capabilities
- **Backend Core:** FastAPI REST API with structured dependency injection, SQLite/PostgreSQL-compatible SQLAlchemy ORM models, role-based governance (Author, Reviewer, Approver, Admin), 21 CFR Part 11 compliant audit logging, and automated change tracking.
- **Ingestion Engine (`apps/api/app/services/ingestion/`):**
  - Modular extractors (`DocxExtractor`, `PdfExtractor`) preserving sequential flow, hierarchical headings, tables, bulleted/numbered lists, and pagination.
  - Scanned PDF detection setting `ocr_required = True`.
  - Rules-based `MetadataExtractor` extracting 13 standard QMS attributes (Title, Document Number, Revision, Effective Date, Review Date, Sign-offs, Purpose, Scope, Responsibilities) with confidence scores and source text citations.
  - `StructureExtractor` building parent-child section trees.
  - `ChunkingEngine` generating structure-aware chunks (max 1200 characters, 150 overlap) with prepended section headers (`### 4.2.4 Control of records\n\n...`).
  - `JsonGenerator` exporting draft-07 validated JSON artifacts to `data/ingested/json/{doc_id}.json`.
  - `LocalAIAdapter` defining the contract for Ollama connectivity and chunk embedding preparation.
- **Frontend Core (`apps/web/`):**
  - React 18 + Vite SPA with complete QMS navigation.
  - `IngestionPage.jsx` providing drag-and-drop file upload, upload status monitoring, metadata inspection with confidence pills, section tree visualization, chunk previews, and JSON artifact export.

### 2.2 Review of Existing Chunk Metadata
In `apps/api/app/models/ingestion.py`, `IngestedChunk` provides comprehensive source provenance:
```python
class IngestedChunk(Base):
    id: Mapped[str]  # e.g. "CHK-E4B28190"
    document_id: Mapped[str]  # FK to ingested_documents.id
    section_id: Mapped[str | None]  # FK to ingested_sections.id
    document_number: Mapped[str | None]  # e.g. "SOP-ASSY-001"
    document_revision: Mapped[str | None]  # e.g. "Rev 2.0"
    section_title: Mapped[str | None]  # e.g. "Control of records"
    section_number: Mapped[str | None]  # e.g. "4.2.4"
    chunk_text: Mapped[str]  # Full chunk text with header
    page_start: Mapped[int | None]  # Start page number
    page_end: Mapped[int | None]  # End page number
    chunk_sequence: Mapped[int]  # 1-indexed order within document
    character_count: Mapped[int]
    token_count_estimate: Mapped[int]
    extraction_status: Mapped[str]  # "success"
    metadata_json: Mapped[dict]
```
**Conclusion:** The existing chunking model is 100% vector-ready. No structural rework of Milestone 2 chunking is needed. Every chunk preserves its document number, section hierarchy, page bounds, and raw text.

---

## 3. PROPOSED MILESTONE 3 ARCHITECTURE

### 3.1 Architectural Diagram

```
+----------------------------------------------------------------------------------------------------+
|                                         AIQMS CLIENT / WEB UI                                      |
|   +-----------------------+    +-----------------------+    +----------------------------------+   |
|   | Document Ingestion UI |    |  Semantic Search View |    | ISO 13485 Traceability Matrix UI |   |
|   +-----------+-----------+    +-----------+-----------+    +-----------------+----------------+   |
+---------------|----------------------------|----------------------------------|--------------------+
                |                            |                                  |
                v                            v                                  v
+----------------------------------------------------------------------------------------------------+
|                                          FASTAPI ROUTERS                                           |
|   +-------------------------------+   +-----------------------------+   +----------------------+   |
|   | /api/v1/vectors/embed/*       |   | /api/v1/search/semantic     |   | /api/v1/compliance/* |   |
|   +---------------+---------------+   +--------------+--------------+   +----------+-----------+   |
+-------------------|----------------------------------|-----------------------------|---------------+
                    |                                  |                             |
                    v                                  v                             v
+----------------------------------------------------------------------------------------------------+
|                                    BACKEND SERVICES & ENGINES                                      |
|                                                                                                    |
|  +--------------------------------+   +--------------------------------+   +--------------------+  |
|  |     OllamaEmbeddingClient      |   |       SemanticSearchEngine     |   |   ISO Traceability |  |
|  |   - nomic-embed-text (768-d)   |   |   - Dense cosine search        |   |   Validator        |  |
|  |   - Search document prefix     |   |   - Metadata filtering         |   |   - qwen3:4b LLM   |  |
|  |   - Batch worker & retry queue |   |   - Section hierarchy rerank   |   |   - Gap evaluation |  |
|  +----------------+---------------+   +--------------+-----------------+   +---------+----------+  |
|                   |                                  |                               |             |
|                   v                                  v                               |             |
|  +-----------------------------------------------------------------------------+     |             |
|  |                         ChromaVectorStoreService                            |     |             |
|  |   - In-Process chromadb.PersistentClient ("data/chroma")                    |     |             |
|  |   - Collections: 'aiqms_document_chunks' & 'iso_13485_clauses'              |     |             |
|  |   - HNSW Cosine Indexing with Provenance Metadata                           |     |             |
|  +-----------------------------------------------------------------------------+     |             |
|                                                                                      |             |
|  +-----------------------------------------------------------------------------+     |             |
|  |                         OllamaReasoningEngine                               | <---+             |
|  |   - Local qwen3:4b instance via /api/generate                               |                   |
|  |   - Zero-temperature deterministic prompt templates                         |                   |
|  |   - Grounded evidence extraction (immutability preserved)                   |                   |
|  +-----------------------------------------------------------------------------+                   |
+----------------------------------------------------------------------------------------------------+
                                               |
                                               v
+----------------------------------------------------------------------------------------------------+
|                                  STORAGE & DATABASE LAYER                                          |
|   +------------------------------------+          +--------------------------------------------+   |
|   |  Relational DB (SQLite/PostgreSQL) |          |  Vector Storage (ChromaDB Local Store)     |   |
|   |  - ingested_chunks (embed status)  |          |  - data/chroma/chroma.sqlite3              |   |
|   |  - iso_clauses (ISO 13485 library) |          |  - data/chroma/{collection_uuid}/*.bin     |   |
|   |  - compliance_traceability_runs    |          +--------------------------------------------+   |
|   |  - compliance_traceability_items   |                                                           |
|   +------------------------------------+                                                           |
+----------------------------------------------------------------------------------------------------+
```

---

## 4. VECTOR STORAGE DESIGN (ChromaDB)

### 4.1 Storage Mode & Directory Structure
ChromaDB will run strictly **in-process** via `chromadb.PersistentClient` pointing to `data/chroma/`. This guarantees:
- Zero external daemon dependencies (no Docker required).
- Completely air-gapped, offline compliance for sensitive medical device IP.
- Atomic ACID transactions on chunk indexing.

Directory layout:
```
data/
└── chroma/
    ├── chroma.sqlite3               <- Metadata index and vector table catalog
    └── [collection-uuid]/          <- HNSW vector graph, index buffers, and segment files
```

### 4.2 Collection Specifications

We define two isolated, specialized collections:

#### Collection 1: `aiqms_document_chunks`
- **Purpose:** Stores embedded chunks from ingested documents (DOCX, PDF, future XLSX).
- **Distance Metric:** Cosine similarity (`{"hnsw:space": "cosine"}`).
- **Document Text Input:**
  Formatted with `search_document:` prefix according to Nomic standard:
  `search_document: [{document_number or 'DOC'}] {chunk_text}`
- **ID Strategy:** Direct mapping to `IngestedChunk.id` (e.g. `CHK-0B1C4EE7`).
- **Chroma Metadata Attributes:**
  ```json
  {
    "document_id": "DOC-8B39B7C7",
    "document_number": "SOP-ASSY-001",
    "document_revision": "1.0",
    "section_id": "SEC-9F8A12B3",
    "section_number": "4.2.4",
    "section_title": "Control of Records",
    "page_start": 4,
    "page_end": 4,
    "chunk_sequence": 12,
    "file_format": "DOCX",
    "organization_id": "default",
    "created_at": "2026-10-30T14:30:00Z"
  }
  ```

#### Collection 2: `iso_13485_clauses`
- **Purpose:** Authoritative reference embeddings of ISO 13485:2016 standard clauses.
- **Distance Metric:** Cosine similarity (`{"hnsw:space": "cosine"}`).
- **Document Text Input:**
  `search_document: [ISO 13485:2016 Clause {clause_number}] {clause_text}`
- **ID Strategy:** Authoritative clause key (e.g. `ISO-13485-4.2.4`, `ISO-13485-7.5.1`).
- **Chroma Metadata Attributes:**
  ```json
  {
    "standard": "ISO 13485:2016",
    "clause_number": "4.2.4",
    "parent_clause": "4.2",
    "clause_title": "Control of records",
    "requires_documented_procedure": true,
    "requires_record": true,
    "category": "Documentation requirements"
  }
  ```

---

## 5. EMBEDDING & RETRIEVAL WORKFLOW

### 5.1 Document Embedding Workflow

```
[Ingested Document with Chunks]
             |
             v
[Read Unindexed Chunks from DB: status = 'pending']
             |
             v
[Format Text with Nomic Prefix: "search_document: [{doc_num}] {text}"]
             |
             v
[Batch Chunks (16 per batch)] ---> [Ollama /api/embed (model: nomic-embed-text)]
                                                 |
                                                 v
                                  [Receive 768-d Float Vectors]
                                                 |
                                                 v
[ChromaDB Collection.upsert(ids, embeddings, metadatas, documents)]
             |
             v
[Update DB: IngestedChunk.embedding_status = 'embedded', embedded_at = now()]
             |
             v
[Update DB: IngestedDocument.vector_status = 'indexed']
```

### 5.2 Semantic Search Workflow

```
[User / Client Search Query] (e.g. "How should assembly equipment be calibrated?")
             |
             v
[Prefix Query: "search_query: How should assembly equipment be calibrated?"]
             |
             v
[Ollama /api/embed: generate 768-d query vector]
             |
             v
[ChromaDB Collection.query(query_embeddings, n_results=top_k, where={filter})]
             |
             v
[ChromaDB returns nearest neighbor chunk IDs and cosine distances]
             |
             v
[Post-Processing & Hybrid Scoring]
  - Convert distance to similarity: score = 1.0 - (distance / 2.0)
  - Boost score if document_number or section_number explicitly matches query terms
  - Join full chunk record from IngestedChunk ORM model
             |
             v
[Return Structured Search Results with Exact Text, Section, Page & Provenance]
```

### 5.3 ISO 13485 AI Traceability & Gap Analysis Workflow

```
[Trigger Traceability Audit for Document (e.g. "DOC-8B39B7C7")]
             |
             v
[Load Authoritative ISO 13485:2016 Clauses from DB]
             |
    +--------+---------------------------------------+
    | Loop through active clauses (e.g. 4.2.4, 7.5.1) |
    +--------+---------------------------------------+
             |
             v
[Embed ISO Clause requirement text as search_query]
             |
             v
[Query ChromaDB 'aiqms_document_chunks' filtered by document_id]
             |
             v
[Retrieve Top 3 Most Relevant Chunks from the Document]
             |
    +--------+-------------------------------------------------------------+
    | If similarity < threshold (0.50):                                    |
    |   Verdict = 'not_addressed', Gap = 'Requirement not covered in SOP'  |
    +--------+-------------------------------------------------------------+
    | If similarity >= threshold:                                          |
    |   Construct Grounded Compliance Prompt with ISO text + Chunk text    |
    |   Invoke Ollama /api/generate with qwen3:4b (temperature: 0.0)       |
    |   Parse JSON Verdict: compliant | partially_compliant | gap_detected |
    |   Extract exact evidence quote and missing elements                  |
    +--------+-------------------------------------------------------------+
             |
             v
[Save Audit Run & Findings to Database: ComplianceTraceabilityRun & Items]
             |
             v
[Generate Complete Traceability Matrix & Findings Summary]
```

---

## 6. DATABASE SCHEMA CHANGES

To support vector state tracking, ISO 13485 clause catalogs, and traceability audit trails, four database schema updates are planned:

### 6.1 Column Additions to Existing Models (Non-Breaking)

#### Updates to `IngestedChunk` (`apps/api/app/models/ingestion.py`):
```python
embedding_status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
# Statuses: 'pending', 'embedding', 'embedded', 'failed'
embedding_model: Mapped[str | None] = mapped_column(String(50), nullable=True, default="nomic-embed-text")
embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
vector_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
```

#### Updates to `IngestedDocument` (`apps/api/app/models/ingestion.py`):
```python
vector_status: Mapped[str] = mapped_column(String(30), default="unindexed", index=True)
# Statuses: 'unindexed', 'indexing', 'indexed', 'failed', 'partial'
vector_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

### 6.2 New Model 1: `ISOClause` (`apps/api/app/models/compliance.py`)
Stores the authoritative ISO 13485 standard requirements library:
```python
class ISOClause(Base):
    __tablename__ = "iso_clauses"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # e.g. "ISO-13485-4.2.4"
    standard: Mapped[str] = mapped_column(String(50), default="ISO 13485:2016", index=True)
    clause_number: Mapped[str] = mapped_column(String(30), unique=True, index=True)  # "4.2.4"
    parent_clause_number: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)  # "4.2"
    title: Mapped[str] = mapped_column(String(300))  # "Control of records"
    clause_text: Mapped[str] = mapped_column(Text)  # Full standard requirement text
    summary_requirements: Mapped[str] = mapped_column(Text)  # Bulleted mandatory elements
    requires_documented_procedure: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_record: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[str] = mapped_column(String(100), default="General")
    embedding_status: Mapped[str] = mapped_column(String(30), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
```

### 6.3 New Model 2: `ComplianceTraceabilityRun` (`apps/api/app/models/compliance.py`)
Tracks an automated AI verification audit session:
```python
class ComplianceTraceabilityRun(Base):
    __tablename__ = "compliance_traceability_runs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: f"RUN-{uuid4().hex[:8].upper()}")
    document_id: Mapped[str] = mapped_column(ForeignKey("ingested_documents.id", ondelete="CASCADE"), index=True)
    standard: Mapped[str] = mapped_column(String(50), default="ISO 13485:2016")
    status: Mapped[str] = mapped_column(String(30), default="running")  # "running", "completed", "failed"
    overall_compliance_score: Mapped[float] = mapped_column(Float, default=0.0)  # Percentage 0.0 - 100.0
    total_clauses_evaluated: Mapped[int] = mapped_column(Integer, default=0)
    compliant_count: Mapped[int] = mapped_column(Integer, default=0)
    partial_count: Mapped[int] = mapped_column(Integer, default=0)
    gap_count: Mapped[int] = mapped_column(Integer, default=0)
    not_applicable_count: Mapped[int] = mapped_column(Integer, default=0)
    summary_findings_json: Mapped[dict] = mapped_column(JSON, default=dict)
    model_name: Mapped[str] = mapped_column(String(50), default="qwen3:4b")
    executed_by: Mapped[str] = mapped_column(String(240), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["ComplianceTraceabilityItem"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="ComplianceTraceabilityItem.clause_number"
    )
```

### 6.4 New Model 3: `ComplianceTraceabilityItem` (`apps/api/app/models/compliance.py`)
Granular audit finding linking an ISO clause to candidate chunks and AI reasoning:
```python
class ComplianceTraceabilityItem(Base):
    __tablename__ = "compliance_traceability_items"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: f"ITM-{uuid4().hex[:8].upper()}")
    run_id: Mapped[str] = mapped_column(ForeignKey("compliance_traceability_runs.id", ondelete="CASCADE"), index=True)
    clause_id: Mapped[str] = mapped_column(ForeignKey("iso_clauses.id"), index=True)
    clause_number: Mapped[str] = mapped_column(String(30), index=True)
    matched_chunk_id: Mapped[str | None] = mapped_column(ForeignKey("ingested_chunks.id", ondelete="SET NULL"), nullable=True)
    similarity_score: Mapped[float] = mapped_column(Float, default=0.0)
    verdict: Mapped[str] = mapped_column(String(30))  # "compliant", "partially_compliant", "gap_detected", "not_addressed"
    ai_reasoning: Mapped[str] = mapped_column(Text)
    evidence_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    gap_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), default="major")  # "critical", "major", "minor", "info"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[ComplianceTraceabilityRun] = relationship(back_populates="items")
```

---

## 7. NEW BACKEND MODULES DESIGN

The following modular services will be created under `apps/api/app/services/`:

```
apps/api/app/
├── services/
│   ├── vector_store/
│   │   ├── __init__.py
│   │   ├── base.py                   <- VectorStore abstract interface
│   │   └── chroma_service.py         <- ChromaDB PersistentClient implementation & fallback
│   ├── embedding/
│   │   ├── __init__.py
│   │   ├── base.py                   <- BaseEmbeddingClient interface
│   │   └── ollama_embedder.py        <- Ollama nomic-embed-text client (batching, retry, 768-d check)
│   ├── retrieval/
│   │   ├── __init__.py
│   │   └── semantic_search.py        <- Hybrid dense search, filtering, rank weighting
│   └── compliance/
│       ├── __init__.py
│       ├── iso_seed_data.py          <- Standard ISO 13485:2016 clause definitions
│       ├── prompt_templates.py       <- Zero-hallucination compliance audit prompts
│       ├── reasoning_client.py       <- Ollama qwen3:4b structured JSON inference
│       └── traceability_service.py   <- Master compliance orchestrator
```

### 7.1 Key Service Contracts

#### `OllamaEmbeddingClient` (`services/embedding/ollama_embedder.py`)
```python
class OllamaEmbeddingClient:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "nomic-embed-text"):
        self.base_url = base_url
        self.model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of document chunk texts using 'search_document:' prefix."""
        ...

    def embed_query(self, query: str) -> list[float]:
        """Embed a search query using 'search_query:' prefix."""
        ...
```

#### `ChromaVectorStoreService` (`services/vector_store/chroma_service.py`)
```python
class ChromaVectorStoreService:
    def __init__(self, persist_dir: str):
        ...

    def upsert_chunks(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> int:
        """Upsert chunk vectors and metadata into 'aiqms_document_chunks' collection."""
        ...

    def query_chunks(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filter_dict: Optional[dict] = None
    ) -> list[dict]:
        """Query nearest neighbor chunks with cosine similarity."""
        ...

    def delete_document_chunks(self, document_id: str) -> int:
        """Purge all indexed vectors for a deleted or re-processed document."""
        ...
```

#### `TraceabilityValidator` (`services/compliance/traceability_service.py`)
```python
class TraceabilityValidator:
    def evaluate_clause_compliance(
        self,
        clause: ISOClause,
        candidate_chunks: list[dict]
    ) -> ComplianceEvaluationResult:
        """Evaluate whether retrieved chunks fulfill ISO requirement using qwen3:4b."""
        ...
```

---

## 8. API ENDPOINT DESIGN

The new endpoints will be exposed under `/api/v1/vectors/`, `/api/v1/search/`, and `/api/v1/compliance/`:

### 8.1 Vector Indexing Endpoints (`vectors_router.py`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/vectors/embed/document/{document_id}` | Generate vectors for all chunks of an ingested document and index them into ChromaDB |
| `POST` | `/api/v1/vectors/embed/batch` | Embed all unindexed chunks across all documents |
| `DELETE` | `/api/v1/vectors/document/{document_id}` | Remove an ingested document's vectors from ChromaDB |
| `GET` | `/api/v1/vectors/status` | Vector store health, collection statistics, and Ollama connection status |

### 8.2 Semantic Search Endpoints (`search_router.py`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/search/semantic` | Query indexed QMS documents with natural language question or requirement |

**Sample Request (`POST /api/v1/search/semantic`):**
```json
{
  "query": "Where are environmental controls and temperature limits specified for assembly?",
  "document_id": null,
  "top_k": 5,
  "min_score": 0.60
}
```

**Sample Response:**
```json
{
  "query": "Where are environmental controls and temperature limits specified for assembly?",
  "total_results": 2,
  "execution_time_ms": 84,
  "results": [
    {
      "chunk_id": "CHK-7A9B1C2D",
      "document_id": "DOC-8B39B7C7",
      "document_number": "SOP-ASSY-001",
      "document_revision": "1.0",
      "section_number": "5.3",
      "section_title": "Environmental Controls",
      "similarity_score": 0.892,
      "page_start": 6,
      "page_end": 6,
      "text": "### 5.3 Environmental Controls\n\nCleanroom temperature shall be maintained between 18°C and 22°C..."
    }
  ]
}
```

### 8.3 ISO 13485 Compliance Endpoints (`compliance_router.py`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/compliance/iso13485/clauses` | List standard ISO 13485:2016 clauses |
| `POST` | `/api/v1/compliance/iso13485/seed` | Seed authoritative ISO 13485 clause database and ChromaDB collection |
| `POST` | `/api/v1/compliance/verify/{document_id}` | Trigger automated ISO 13485 gap analysis using semantic retrieval + `qwen3:4b` |
| `GET` | `/api/v1/compliance/runs/{run_id}` | Get full report and findings breakdown for a traceability run |
| `GET` | `/api/v1/compliance/matrix/{document_id}` | Get complete clause-to-SOP traceability matrix |

---

## 9. TESTING STRATEGY

Milestone 3 will implement a multi-tiered test suite following the strict zero-regression standard:

### 9.1 Unit Testing
- `test_ollama_embedder.py`: Test formatting of `search_document:` and `search_query:` prefixes, batch processing, 768-dimensional output validation, and fallback error handling when Ollama is unreachable.
- `test_chroma_service.py`: Test ChromaDB persistent initialization, collection creation, vector upsert, distance calculations, metadata filtering, and deletion.
- `test_semantic_retriever.py`: Test top-k ordering, score cutoff thresholds, and keyword-boosting logic.
- `test_compliance_prompts.py`: Verify prompt string rendering, JSON schema enforcement for `qwen3:4b`, and handling of non-compliant verdicts.

### 9.2 Integration Testing
- `test_end_to_end_vector_pipeline.py`: Upload sample DOCX (`sample_documents/Device assembly.docx`) -> chunk -> generate embeddings with live Ollama -> query semantic search -> verify top match is accurate.
- `test_iso_traceability_evaluation.py`: Run ISO 13485 clause 7.5.1 (Control of production) against the assembly SOP using local `qwen3:4b` and verify returned structured JSON verdict and citation.

### 9.3 Failure, Boundary & Security Testing
- **Ollama Timeout / Offline Handling:** When Ollama is stopped, the API must return clean 503/400 errors without hanging worker threads.
- **Corrupted / Empty Chunks:** Ensure chunks with only whitespace are safely skipped without vector store pollution.
- **Idempotency:** Re-indexing a document replaces existing chunk vectors cleanly without duplication.
- **AI Immutability Guarantee:** Rigorously verify that the LLM has zero capability or write permissions to modify original document text, approval statuses, or metadata.

### 9.4 Regression Testing
- Execute all 32 existing tests from Milestone 1 and Milestone 2 to guarantee zero regression across templates, documents, validation, audit trail, and ingestion.

---

## 10. RISKS & IMPLEMENTATION DEPENDENCIES

| Risk / Dependency | Impact | Probability | Mitigation Strategy |
|---|---|---|---|
| **`chromadb` Virtualenv Installation** | High | Low | `chromadb` is not currently in the virtual environment. We will verify compatibility with Python 3.13.2. If any binary wheel issues arise on Windows, an SQLite-native vector fallback (cosine similarity via `numpy` or `sqlite-vec`) will be provided seamlessly behind the `VectorStore` interface. |
| **Ollama Model Cold-Start Latency** | Medium | Medium | The first call to `nomic-embed-text` took 7.39s to load model weights into VRAM. After warming up, it responded in ~1.6s. We will implement background model warm-up on API startup and batch chunk requests (16-32 chunks per batch) to maximize throughput. |
| **LLM Hallucinations in Compliance** | Critical | Low | QMS compliance strictly prohibits artificial approvals or fabricated SOP text. We mandate `temperature: 0.0`, strict few-shot JSON formatting prompts, and explicit instructions requiring literal text quotations from retrieved chunks. Missing requirements are strictly classified as `gap_detected` or `not_addressed`. |
| **Resource Contention (VRAM/RAM)** | Medium | Low | `qwen3:4b` requires ~2.5 GB and `nomic-embed-text` requires ~270 MB. The system has confirmed sufficient headroom. Background embedding workers will run sequentially rather than concurrently to prevent GPU memory spikes. |
| **Air-Gapped / Offline Guarantee** | Critical | Low | All model calls route strictly to `http://localhost:11434`. No external API keys (OpenAI, Anthropic, Google Cloud) are required or allowed in the embedding or compliance pipeline. |

---

## 11. NEXT STEPS & APPROVAL CHECKLIST

The preparation tasks are complete. To proceed with the implementation of Milestone 3, the following sequence will be followed upon user approval:

- [ ] **Step 1:** Install/configure `chromadb` (or vector storage fallback) in `apps/api/.venv`.
- [ ] **Step 2:** Apply database schema additions (`IngestedChunk`, `IngestedDocument`, `ISOClause`, `ComplianceTraceabilityRun`, `ComplianceTraceabilityItem`).
- [ ] **Step 3:** Implement backend services: `OllamaEmbeddingClient`, `ChromaVectorStoreService`, `SemanticSearchEngine`, and `TraceabilityValidator`.
- [ ] **Step 4:** Implement and mount API routers (`/api/v1/vectors`, `/api/v1/search`, `/api/v1/compliance`).
- [ ] **Step 5:** Seed ISO 13485:2016 standard clause library.
- [ ] **Step 6:** Build frontend Semantic Search & ISO Traceability Matrix UI tabs.
- [ ] **Step 7:** Run comprehensive automated test suite and generate Milestone 3 verification report.

---
*Report generated and architecture designed by AIQMS Engineering Team. Awaiting user approval to proceed with Milestone 3 implementation.*
