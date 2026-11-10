"""Tests for Milestone 3.4: ISO 13485:2016 Knowledge Base.

Verifies:
- Clause numbering and total canonical clause count (88 clauses).
- Complete clause hierarchy and parent-child integrity.
- Text completeness, normative text and explanatory notes distinction.
- Page references preservation.
- Duplicate clause prevention.
- Vector embedding and ChromaDB retrieval.
- Semantic search accuracy on authoritative ISO requirements.
- API endpoints.
"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import Base, SessionLocal, engine
from app.db.migrations import run_migrations
from app.models.compliance import ISOClause
from app.services.compliance.iso_pdf_extractor import ISOPdfExtractor
from app.services.compliance.iso_knowledge_service import ISOKnowledgeService


@pytest.fixture(scope="module")
def db_session():
    Base.metadata.create_all(bind=engine)
    run_migrations(engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestISOPdfExtraction:
    """Verify PDF extraction directly against sample_documents/ISO-13485-2016-EN.pdf."""

    def test_extract_all_canonical_clauses(self):
        extractor = ISOPdfExtractor()
        clauses = extractor.extract_clauses()

        # ISO 13485:2016 contains exactly 88 canonical clauses in Clauses 1 through 8
        assert len(clauses) == 88

        clause_numbers = [c.clause_number for c in clauses]
        # Check major sections are present
        for expected in ["1", "2", "3", "4", "4.1", "4.2", "4.2.3", "4.2.4", "4.2.5",
                         "5", "5.1", "5.6.1", "6", "6.2", "7", "7.1", "7.3.2", "7.5.6",
                         "7.5.7", "7.5.9.1", "7.5.9.2", "8", "8.2.1", "8.3.2", "8.5.3"]:
            assert expected in clause_numbers, f"Missing expected clause {expected}"

    def test_clause_hierarchy_and_levels(self):
        extractor = ISOPdfExtractor()
        clauses = extractor.extract_clauses()
        by_num = {c.clause_number: c for c in clauses}

        # Level 1 root clauses
        root_clauses = [c for c in clauses if c.level == 1]
        assert len(root_clauses) == 8
        for r in root_clauses:
            assert r.parent_clause_number is None

        # Level 3 subclause child-parent verification
        c424 = by_num["4.2.4"]
        assert c424.level == 3
        assert c424.parent_clause_number == "4.2"
        assert c424.title == "Control of documents"

        # Level 4 subclauses
        c7591 = by_num["7.5.9.1"]
        assert c7591.level == 4
        assert c7591.parent_clause_number == "7.5.9"
        assert c7591.title == "General"

        c7592 = by_num["7.5.9.2"]
        assert c7592.level == 4
        assert c7592.parent_clause_number == "7.5.9"
        assert "implantable" in c7592.title.lower()

    def test_page_references_preservation(self):
        extractor = ISOPdfExtractor()
        clauses = extractor.extract_clauses()
        by_num = {c.clause_number: c for c in clauses}

        # PDF page numbers in source PDF
        c1 = by_num["1"]
        assert c1.page_start == 9  # Scope starts on PDF page 9 (document page 1)

        c423 = by_num["4.2.3"]
        assert c423.page_start >= 14 and c423.page_end <= 16

        c757 = by_num["7.5.7"]
        assert c757.page_start >= 26 and c757.page_end <= 28

        c853 = by_num["8.5.3"]
        assert c853.page_start >= 32 and c853.page_end <= 35

    def test_explanatory_notes_separation(self):
        extractor = ISOPdfExtractor()
        clauses = extractor.extract_clauses()
        by_num = {c.clause_number: c for c in clauses}

        # Clause 7.5.7 contains a NOTE referencing ISO 11607-1 and ISO 11607-2
        c757 = by_num["7.5.7"]
        assert c757.explanatory_notes is not None
        assert "ISO 11607" in c757.explanatory_notes
        # Normative text should not contain the note
        assert "validation of processes for sterilization" in c757.normative_text

        # Clause 7.6 contains a NOTE referencing ISO 10012
        c76 = by_num["7.6"]
        assert c76.explanatory_notes is not None
        assert "ISO 10012" in c76.explanatory_notes

    def test_procedure_and_record_flags(self):
        extractor = ISOPdfExtractor()
        clauses = extractor.extract_clauses()
        by_num = {c.clause_number: c for c in clauses}

        # 4.2.4 Control of documents requires a documented procedure
        assert by_num["4.2.4"].requires_documented_procedure is True

        # 7.5.7 requires documented procedures
        assert by_num["7.5.7"].requires_documented_procedure is True

        # 7.5.6 requires records
        assert by_num["7.5.6"].requires_record is True


class TestISOKnowledgeBaseService:
    """Verify synchronization, deduplication, ChromaDB embedding and retrieval."""

    def test_sync_and_duplicate_prevention(self, db_session: Session):
        service = ISOKnowledgeService(db=db_session)
        # First sync
        stats1 = service.sync_iso_knowledge_base(force_reindex=False)
        assert stats1["status"] == "success"
        assert stats1["total_clauses"] == 88

        # Count in DB
        db_count = db_session.query(ISOClause).count()
        assert db_count == 88

        # Re-sync should detect existing hashes and skip duplicate inserts
        stats2 = service.sync_iso_knowledge_base(force_reindex=False)
        assert stats2["status"] == "success"
        assert stats2["newly_created"] == 0
        assert stats2["skipped"] == 88
        assert db_session.query(ISOClause).count() == 88

    def test_single_clause_detail_with_relationships(self, db_session: Session):
        service = ISOKnowledgeService(db=db_session)
        detail = service.get_clause_by_number("4.2.4")
        assert detail is not None
        assert detail["clause_number"] == "4.2.4"
        assert detail["title"] == "Control of documents"
        assert detail["parent"] is not None
        assert detail["parent"]["clause_number"] == "4.2"
        assert detail["requires_documented_procedure"] is True
        assert detail["page_start"] is not None

    def test_hierarchy_tree_structure(self, db_session: Session):
        service = ISOKnowledgeService(db=db_session)
        tree = service.get_hierarchy_tree()

        # Top level has exactly 8 sections (1 to 8)
        assert len(tree) == 8
        section_nums = [node["clause_number"] for node in tree]
        assert section_nums == ["1", "2", "3", "4", "5", "6", "7", "8"]

        # Quality management system (clause 4) has 2 subclauses: 4.1, 4.2
        c4 = next(n for n in tree if n["clause_number"] == "4")
        c4_children = [ch["clause_number"] for ch in c4["children"]]
        assert "4.1" in c4_children
        assert "4.2" in c4_children

        # 4.2 has 5 subclauses: 4.2.1 through 4.2.5
        c42 = next(ch for ch in c4["children"] if ch["clause_number"] == "4.2")
        c42_children = [ch["clause_number"] for ch in c42["children"]]
        assert c42_children == ["4.2.1", "4.2.2", "4.2.3", "4.2.4", "4.2.5"]

    def test_semantic_clause_search(self, db_session: Session):
        service = ISOKnowledgeService(db=db_session)
        # Search for sterilization validation
        results = service.search_clauses("sterilization and sterile barrier validation", top_k=3)
        assert len(results) > 0
        top_match = results[0]
        assert top_match["clause_number"] == "7.5.7"
        assert "sterilization" in top_match["title"].lower()
        assert top_match["similarity_score"] > 0.50
        assert top_match["page_start"] is not None

        # Search for medical device file
        results2 = service.search_clauses("medical device file specifications and manufacturing procedures", top_k=3)
        assert len(results2) > 0
        clause_nums = [r["clause_number"] for r in results2]
        assert "4.2.3" in clause_nums


class TestISOKnowledgeAPI:
    """Verify FastAPI compliance router endpoints."""

    def test_get_iso_clauses_list(self, client: TestClient):
        res = client.get("/api/v1/compliance/iso13485/clauses")
        assert res.status_code == 200
        data = res.json()
        assert data["total_clauses"] == 88
        assert len(data["clauses"]) == 88

    def test_get_iso_clauses_filtered_by_category(self, client: TestClient):
        res = client.get("/api/v1/compliance/iso13485/clauses?category=Resource management")
        assert res.status_code == 200
        data = res.json()
        assert data["total_clauses"] > 0
        for c in data["clauses"]:
            assert c["category"] == "Resource management"

    def test_get_iso_clause_by_number_endpoint(self, client: TestClient):
        res = client.get("/api/v1/compliance/iso13485/clauses/7.5.6")
        assert res.status_code == 200
        data = res.json()
        assert data["clause_number"] == "7.5.6"
        assert "validation of processes" in data["title"].lower()
        assert data["level"] == 3
        assert data["parent"]["clause_number"] == "7.5"

    def test_get_iso_hierarchy_tree_endpoint(self, client: TestClient):
        res = client.get("/api/v1/compliance/iso13485/hierarchy")
        assert res.status_code == 200
        data = res.json()
        assert len(data["tree"]) == 8

    def test_search_iso_clauses_api(self, client: TestClient):
        payload = {
            "query": "management review inputs and outputs",
            "top_k": 3,
            "min_score": 0.3
        }
        res = client.post("/api/v1/compliance/iso13485/search", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["total_results"] > 0
        matched_numbers = [r["clause_number"] for r in data["results"]]
        assert any(n.startswith("5.6") for n in matched_numbers)
