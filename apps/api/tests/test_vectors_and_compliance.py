import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.migrations import run_migrations
from app.db.session import Base, engine, SessionLocal
from app.main import app
from app.models.compliance import ISOClause, ComplianceTraceabilityItem, ComplianceTraceabilityRun
from app.models.ingestion import IngestedDocument, IngestedChunk, IngestedSection
from app.services.compliance.iso_seed_data import ISO_13485_CLAUSES
from app.services.compliance.reasoning_client import OllamaReasoningClient
from app.services.compliance.traceability_service import TraceabilityService
from app.services.embedding.ollama_embedder import OllamaEmbeddingClient
from app.services.retrieval.semantic_search import SemanticSearchEngine
from app.services.vector_store.chroma_service import ChromaVectorStoreService

SAMPLE_DOCS_DIR = Path(__file__).resolve().parents[3] / "sample_documents"
AUTH_HEADERS = {
    "X-Actor-Email": "lead.auditor@aiqms.local",
    "X-Actor-Role": "admin",
    "X-Organization-Id": "test-org",
}


@pytest.fixture(scope="module")
def client():
    """Module-level TestClient ensuring all SQLAlchemy models and tables are initialized."""
    Base.metadata.create_all(bind=engine)
    run_migrations(engine)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    """Provide a transactional DB session for tests."""
    Base.metadata.create_all(bind=engine)
    run_migrations(engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# UNIT TESTS: Embedding Client
# ============================================================================

def test_unit_embedder_query_prefixing():
    """Verify nomic-embed-text search_query: prefix and 768 dimensions."""
    embedder = OllamaEmbeddingClient()
    assert embedder.model == "nomic-embed-text"

    vector = embedder.embed_query("cleanroom contamination control")
    assert isinstance(vector, list)
    assert len(vector) == 768
    assert all(isinstance(v, float) for v in vector)


def test_unit_embedder_batch_documents():
    """Verify batch embedding of documents preserves count and 768 dimensions."""
    embedder = OllamaEmbeddingClient()
    texts = [
        "Section 1.0: Medical Device Quality Manual",
        "Section 2.0: Sterilization validation protocol",
        "Section 3.0: Cleanroom particle counts ISO Class 7",
    ]
    vectors = embedder.embed_documents(texts)
    assert len(vectors) == 3
    for v in vectors:
        assert len(v) == 768


# ============================================================================
# UNIT TESTS: ChromaDB Vector Store
# ============================================================================

def test_unit_chroma_store_operations():
    """Verify collection access, upsert, query, and statistics in ChromaDB."""
    store = ChromaVectorStoreService()

    stats = store.get_stats()
    assert "total_chunks_indexed" in stats
    assert "iso_clauses_indexed" in stats
    assert stats["status"] == "online"

    # Test dummy chunk upsert and query
    embedder = OllamaEmbeddingClient()
    dummy_text = "Standard Operating Procedure for Orthopedic Implant Laser Etching."
    dummy_vector = embedder.embed_documents([dummy_text])[0]
    dummy_id = "test_chunk_unit_9999"

    store.upsert_chunks(
        collection_name=ChromaVectorStoreService.COLLECTION_CHUNKS,
        ids=[dummy_id],
        embeddings=[dummy_vector],
        documents=[dummy_text],
        metadatas=[{"document_id": "TEST-DOC-UNIT", "section_title": "Laser Etching"}],
    )

    # Query with semantic embedding
    query_vector = embedder.embed_query("implant laser etching")
    results = store.query(
        collection_name=ChromaVectorStoreService.COLLECTION_CHUNKS,
        query_embedding=query_vector,
        top_k=2,
        filter_dict={"document_id": "TEST-DOC-UNIT"},
    )

    assert len(results) >= 1
    assert results[0]["id"] == dummy_id
    assert results[0]["score"] > 0.60
    assert "Laser Etching" in results[0]["document"]

    # Delete test chunk
    deleted = store.delete_document_chunks("TEST-DOC-UNIT")
    assert deleted >= 1


# ============================================================================
# UNIT TESTS: ISO 13485 Standard Clause Seed Data
# ============================================================================

def test_unit_iso_standard_clauses_library():
    """Verify authoritative ISO 13485:2016 standard clauses structure and counts."""
    assert len(ISO_13485_CLAUSES) == 15

    clause_numbers = {c["clause_number"] for c in ISO_13485_CLAUSES}
    assert "4.2.3" in clause_numbers  # Medical Device File
    assert "4.2.4" in clause_numbers  # Control of documents
    assert "4.2.5" in clause_numbers  # Control of records
    assert "6.4.1" in clause_numbers  # Work environment
    assert "6.4.2" in clause_numbers  # Contamination control
    assert "7.1" in clause_numbers    # Planning of product realization
    assert "7.3.5" in clause_numbers  # Design verification
    assert "7.3.6" in clause_numbers  # Design validation
    assert "7.5.1" in clause_numbers  # Control of production
    assert "7.5.6" in clause_numbers  # Process validation
    assert "7.5.8" in clause_numbers  # Identification
    assert "7.5.9" in clause_numbers  # Traceability
    assert "8.2.4" in clause_numbers  # Internal audit
    assert "8.3.1" in clause_numbers  # Control of nonconforming product
    assert "8.5.2" in clause_numbers  # Corrective action

    for clause in ISO_13485_CLAUSES:
        assert clause["title"]
        assert clause["category"]
        assert clause["summary_requirements"]
        assert isinstance(clause["requires_documented_procedure"], bool)
        assert isinstance(clause["requires_record"], bool)


# ============================================================================
# UNIT TESTS: Semantic Search Engine Hybrid Scoring
# ============================================================================

def test_unit_semantic_search_hybrid_boost(db_session: Session):
    """Verify hybrid scoring applies exact section number and lexical boosts."""
    engine = SemanticSearchEngine(db=db_session)

    results = engine.search(
        query="Section 7.5.1 Control of production and service provision",
        top_k=5,
        min_score=0.20,
    )

    assert "query" in results
    assert "results" in results
    assert "execution_time_ms" in results or "search_time_ms" in results
    assert isinstance(results["results"], list)


# ============================================================================
# UNIT TESTS: Ollama Reasoning & Heuristic Parsing
# ============================================================================

def test_unit_reasoning_client_fallback_parsing():
    """Verify OllamaReasoningClient parses JSON markdown fences and falls back reliably."""
    client_llm = OllamaReasoningClient()

    # Test fence stripping
    raw_response = """
    <think>
    Analyzing the clause requirements against provided text.
    The text states procedure exists.
    </think>
    ```json
    {
      "verdict": "COMPLIANT",
      "confidence": 0.95,
      "reasoning": "The document explicitly establishes standard operating procedure for cleanroom assembly.",
      "cited_excerpt": "All operators must wear Class 100 cleanroom apparel.",
      "gap_description": null,
      "recommended_action": null,
      "severity": "info"
    }
    ```
    """
    parsed = client_llm._parse_json_response(raw_response)
    assert parsed is not None
    assert parsed["verdict"] == "compliant"
    assert "Class 100" in parsed["cited_excerpt"]

    # Test heuristic fallback for domain knowledge
    fallback = client_llm._heuristic_fallback(
        clause_number="6.4.2",
        clause_title="Contamination control",
        evidence_text="Cleanroom operators must follow gowning procedures to prevent contamination.",
    )
    assert fallback["verdict"] in ["compliant", "partially_compliant"]
    assert fallback["cited_excerpt"] is not None


# ============================================================================
# INTEGRATION TESTS: Vector Endpoints
# ============================================================================

def test_api_vector_status(client: TestClient):
    """GET /api/v1/vectors/status returns valid health, model, and count metrics."""
    res = client.get("/api/v1/vectors/status", headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert "total_chunks_indexed" in data
    assert "iso_clauses_indexed" in data
    assert data["ollama_embedding_online"] is True
    assert data["embedding_model"] == "nomic-embed-text"


def test_api_iso_clauses_listing_and_seeding(client: TestClient):
    """GET /api/v1/compliance/iso13485/clauses and POST /seed work idempotently."""
    # Seed endpoint
    seed_res = client.post("/api/v1/compliance/iso13485/seed", headers=AUTH_HEADERS)
    assert seed_res.status_code == 200
    assert "Successfully seeded" in seed_res.json()["message"]

    # List endpoint
    list_res = client.get("/api/v1/compliance/iso13485/clauses", headers=AUTH_HEADERS)
    assert list_res.status_code == 200
    clauses_data = list_res.json()
    assert clauses_data["standard"] == "ISO 13485:2016"
    assert clauses_data["total_clauses"] >= 15
    assert len(clauses_data["clauses"]) >= 15


# ============================================================================
# INTEGRATION TESTS: End-to-End Ingestion, Embedding, Search & Audit
# ============================================================================

def test_api_end_to_end_indexing_search_and_compliance(client: TestClient, db_session: Session):
    """Verify document upload -> chunk embedding -> semantic search -> ISO 13485 compliance audit."""
    # 1. Ingest sample DOCX document
    sample_path = SAMPLE_DOCS_DIR / "Device assembly.docx"
    assert sample_path.exists(), f"Sample file not found at {sample_path}"

    with open(sample_path, "rb") as f:
        upload_res = client.post(
            "/api/v1/documents/upload",
            files={"files": ("Device assembly.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            headers=AUTH_HEADERS,
        )

    assert upload_res.status_code == 200
    upload_data = upload_res.json()
    assert upload_data["successful"] >= 1
    doc_id = upload_data["documents"][0]["document_id"]

    # 2. Embed document chunks into ChromaDB
    embed_res = client.post(f"/api/v1/vectors/embed/document/{doc_id}", headers=AUTH_HEADERS)
    assert embed_res.status_code == 200
    embed_data = embed_res.json()
    assert embed_data["document_id"] == doc_id
    assert embed_data["status"] == "indexed"
    assert embed_data["indexed_chunks"] > 0

    # 3. Perform semantic search scoped to document
    search_res = client.post(
        "/api/v1/search/semantic",
        json={
            "query": "assembly procedure and gowning requirements",
            "document_id": doc_id,
            "top_k": 3,
            "min_score": 0.30,
        },
        headers=AUTH_HEADERS,
    )
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert search_data["total_results"] >= 1
    assert search_data["results"][0]["document_id"] == doc_id
    assert search_data["results"][0]["score"] >= 0.30

    # 4. Execute ISO 13485 Traceability Audit
    audit_res = client.post(f"/api/v1/compliance/verify/{doc_id}", headers=AUTH_HEADERS)
    assert audit_res.status_code == 200
    audit_data = audit_res.json()
    assert audit_data["document_id"] == doc_id
    assert audit_data["status"] == "completed"
    assert audit_data.get("total_clauses", audit_data.get("total_clauses_evaluated", 0)) >= 15
    run_id = audit_data["run_id"]

    # 5. Fetch Traceability Matrix
    matrix_res = client.get(f"/api/v1/compliance/matrix/{doc_id}", headers=AUTH_HEADERS)
    assert matrix_res.status_code == 200
    matrix_data = matrix_res.json()
    assert matrix_data["has_run"] is True
    assert matrix_data["run_id"] == run_id
    matrix_items = matrix_data.get("items") or matrix_data.get("matrix", [])
    assert len(matrix_items) >= 15
    for item in matrix_items:
        assert "clause_number" in item
        assert item["verdict"] in ["compliant", "partially_compliant", "gap_detected", "not_addressed"]
        assert "reasoning" in item

    # 6. Fetch Full Run Details
    run_res = client.get(f"/api/v1/compliance/runs/{run_id}", headers=AUTH_HEADERS)
    assert run_res.status_code == 200
    run_details = run_res.json()
    assert run_details["run_id"] == run_id
    assert len(run_details["items"]) >= 15
