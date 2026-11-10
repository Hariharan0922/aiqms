"""ISO 13485:2016 Knowledge Base Service.

Orchestrates PDF extraction, PostgreSQL persistence, ChromaDB vector indexing,
hierarchical tree generation, and semantic retrieval for ISO 13485:2016 clauses.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
try:
    import chromadb
except ImportError:
    chromadb = None

from app.core.config import settings
from app.models.compliance import ISOClause
from app.services.compliance.iso_pdf_extractor import ISOPdfExtractor, ExtractedISOClause
from app.services.embedding.ollama_embedder import OllamaEmbeddingClient, OllamaEmbeddingError
from app.services.retrieval.semantic_search import ServiceUnavailableError
from app.services.vector_store.chroma_service import ChromaVectorStoreService

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ISOKnowledgeService:
    """Enterprise service managing the ISO 13485:2016 knowledge repository."""

    COLLECTION_NAME = "aiqms_iso_clauses"

    def __init__(
        self,
        db: Session,
        embedder: Optional[OllamaEmbeddingClient] = None,
        vector_store: Optional[ChromaVectorStoreService] = None,
        extractor: Optional[ISOPdfExtractor] = None,
    ):
        self.db = db
        self.embedder = embedder or OllamaEmbeddingClient()
        self.vector_store = vector_store or ChromaVectorStoreService()
        self.extractor = extractor or ISOPdfExtractor()

        # Connect or create ISO clause collection in ChromaDB
        if self.vector_store._client:
            self._iso_collection = self.vector_store._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"description": "Authoritative ISO 13485:2016 standard clauses"},
            )
        else:
            self._iso_collection = None

    def sync_iso_knowledge_base(self, force_reindex: bool = False) -> Dict[str, Any]:
        """Extract ISO 13485 clauses from primary source PDF, store in PostgreSQL, and index in ChromaDB."""
        logger.info("Starting ISO 13485:2016 Knowledge Base synchronization...")
        extracted_clauses = self.extractor.extract_clauses()

        created_count = 0
        updated_count = 0
        skipped_count = 0
        clauses_to_embed: List[ISOClause] = []

        for c in extracted_clauses:
            existing = self.db.query(ISOClause).filter_by(clause_number=c.clause_number).first()
            if not existing:
                new_clause = ISOClause(
                    id=c.clause_id,
                    standard="ISO 13485:2016",
                    clause_number=c.clause_number,
                    parent_clause_number=c.parent_clause_number,
                    level=c.level,
                    title=c.title,
                    category=c.category,
                    clause_text=c.clause_text,
                    normative_text=c.normative_text,
                    explanatory_notes=c.explanatory_notes,
                    is_normative=c.is_normative,
                    summary_requirements=c.summary_requirements,
                    requires_documented_procedure=c.requires_documented_procedure,
                    requires_record=c.requires_record,
                    page_start=c.page_start,
                    page_end=c.page_end,
                    subclauses_count=len(c.subclauses),
                    content_hash=c.content_hash,
                    embedding_status="pending",
                )
                self.db.add(new_clause)
                created_count += 1
                clauses_to_embed.append(new_clause)
            else:
                # Update existing record
                has_changed = existing.content_hash != c.content_hash
                existing.parent_clause_number = c.parent_clause_number
                existing.level = c.level
                existing.title = c.title
                existing.category = c.category
                existing.clause_text = c.clause_text
                existing.normative_text = c.normative_text
                existing.explanatory_notes = c.explanatory_notes
                existing.is_normative = c.is_normative
                existing.summary_requirements = c.summary_requirements
                existing.requires_documented_procedure = c.requires_documented_procedure
                existing.requires_record = c.requires_record
                existing.page_start = c.page_start
                existing.page_end = c.page_end
                existing.subclauses_count = len(c.subclauses)
                existing.content_hash = c.content_hash

                if has_changed or force_reindex or existing.embedding_status != "completed":
                    existing.embedding_status = "pending"
                    clauses_to_embed.append(existing)
                    updated_count += 1
                else:
                    skipped_count += 1

        self.db.commit()

        # Generate embeddings and store in ChromaDB
        embedded_count = 0
        embedding_errors = 0
        if clauses_to_embed:
            if not self.embedder.is_available():
                logger.warning("Ollama embedder is currently unavailable; clause embedding deferred.")
            else:
                # Batch embed clauses
                batch_size = 10
                for i in range(0, len(clauses_to_embed), batch_size):
                    batch = clauses_to_embed[i : i + batch_size]
                    batch_texts = [
                        f"ISO 13485:2016 Clause {clause.clause_number}: {clause.title}\n{clause.normative_text or clause.clause_text}"
                        for clause in batch
                    ]
                    batch_ids = [clause.id for clause in batch]
                    batch_metas = [
                        {
                            "clause_number": clause.clause_number,
                            "parent_clause_number": clause.parent_clause_number or "",
                            "title": clause.title,
                            "category": clause.category,
                            "level": int(clause.level),
                            "page_start": int(clause.page_start or 0),
                            "page_end": int(clause.page_end or 0),
                            "requires_procedure": bool(clause.requires_documented_procedure),
                            "requires_record": bool(clause.requires_record),
                        }
                        for clause in batch
                    ]

                    try:
                        embeddings = self.embedder.embed_documents(batch_texts)
                        self._iso_collection.upsert(
                            ids=batch_ids,
                            embeddings=embeddings,
                            documents=batch_texts,
                            metadatas=batch_metas,
                        )
                        now = utcnow()
                        for clause in batch:
                            clause.embedding_status = "completed"
                            clause.vector_id = clause.id
                            clause.embedded_at = now
                            embedded_count += 1
                        self.db.commit()
                    except Exception as exc:
                        logger.error("Error embedding clause batch: %s", exc)
                        embedding_errors += len(batch)
                        for clause in batch:
                            clause.embedding_status = "failed"
                        self.db.commit()

        return {
            "status": "success",
            "total_clauses": len(extracted_clauses),
            "newly_created": created_count,
            "updated": updated_count,
            "skipped": skipped_count,
            "embedded": embedded_count,
            "embedding_errors": embedding_errors,
            "chroma_total": self._iso_collection.count(),
        }

    def search_clauses(
        self,
        query: str,
        top_k: int = 5,
        category: Optional[str] = None,
        level: Optional[int] = None,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Semantic search over ISO 13485 clauses with authoritative PostgreSQL data."""
        clean_query = query.strip()
        if not clean_query:
            return []

        if not self.embedder.is_available():
            raise ServiceUnavailableError("Ollama embedding service is currently unavailable.")

        try:
            query_embedding = self.embedder.embed_query(clean_query)
        except Exception as exc:
            raise ServiceUnavailableError(f"Failed to generate query embedding: {exc}")

        # Build metadata where filter
        where_filter: Dict[str, Any] = {}
        conditions = []
        if category:
            conditions.append({"category": category})
        if level is not None:
            conditions.append({"level": int(level)})

        if len(conditions) == 1:
            where_filter = conditions[0]
        elif len(conditions) > 1:
            where_filter = {"$and": conditions}

        fetch_k = min(max(top_k * 2, 10), 50)
        query_kwargs: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": min(fetch_k, max(self._iso_collection.count(), 1)),
            "include": ["distances", "metadatas", "documents"],
        }
        if where_filter:
            query_kwargs["where"] = where_filter

        try:
            chroma_results = self._iso_collection.query(**query_kwargs)
        except Exception as exc:
            raise ServiceUnavailableError(f"ChromaDB retrieval error: {exc}")

        ids = chroma_results.get("ids", [[]])[0]
        distances = chroma_results.get("distances", [[]])[0]

        if not ids:
            return []

        # Authoritative PostgreSQL lookup
        clauses_by_id = {
            c.id: c for c in self.db.query(ISOClause).filter(ISOClause.id.in_(ids)).all()
        }

        results: List[Dict[str, Any]] = []
        for clause_id, distance in zip(ids, distances):
            clause = clauses_by_id.get(clause_id)
            if not clause:
                continue

            # Convert cosine distance to similarity score
            sim_score = max(0.0, round(1.0 - (float(distance) / 2.0), 4))
            if sim_score < min_score:
                continue

            results.append(
                {
                    "clause_id": clause.id,
                    "clause_number": clause.clause_number,
                    "parent_clause_number": clause.parent_clause_number,
                    "level": clause.level,
                    "title": clause.title,
                    "category": clause.category,
                    "similarity_score": sim_score,
                    "cosine_distance": round(float(distance), 4),
                    "page_start": clause.page_start,
                    "page_end": clause.page_end,
                    "requires_documented_procedure": clause.requires_documented_procedure,
                    "requires_record": clause.requires_record,
                    "is_normative": clause.is_normative,
                    "normative_text": clause.normative_text,
                    "explanatory_notes": clause.explanatory_notes,
                    "summary_requirements": clause.summary_requirements,
                }
            )

            if len(results) >= top_k:
                break

        return results

    def get_clause_by_number(self, clause_number: str) -> Optional[Dict[str, Any]]:
        """Retrieve single clause details with parent and subclause relationships."""
        clause = self.db.query(ISOClause).filter_by(clause_number=clause_number).first()
        if not clause:
            return None

        # Fetch parent
        parent = None
        if clause.parent_clause_number:
            p_clause = (
                self.db.query(ISOClause)
                .filter_by(clause_number=clause.parent_clause_number)
                .first()
            )
            if p_clause:
                parent = {
                    "clause_number": p_clause.clause_number,
                    "title": p_clause.title,
                    "level": p_clause.level,
                }

        # Fetch children
        children = (
            self.db.query(ISOClause)
            .filter_by(parent_clause_number=clause.clause_number)
            .order_by(ISOClause.clause_number)
            .all()
        )
        subclauses = [
            {
                "clause_number": ch.clause_number,
                "title": ch.title,
                "level": ch.level,
                "requires_procedure": ch.requires_documented_procedure,
                "requires_record": ch.requires_record,
            }
            for ch in children
        ]

        return {
            "clause_id": clause.id,
            "standard": clause.standard,
            "clause_number": clause.clause_number,
            "parent_clause_number": clause.parent_clause_number,
            "parent": parent,
            "subclauses": subclauses,
            "subclauses_count": len(subclauses),
            "level": clause.level,
            "title": clause.title,
            "category": clause.category,
            "clause_text": clause.clause_text,
            "normative_text": clause.normative_text,
            "explanatory_notes": clause.explanatory_notes,
            "is_normative": clause.is_normative,
            "summary_requirements": clause.summary_requirements,
            "requires_documented_procedure": clause.requires_documented_procedure,
            "requires_record": clause.requires_record,
            "page_start": clause.page_start,
            "page_end": clause.page_end,
            "embedding_status": clause.embedding_status,
            "content_hash": clause.content_hash,
        }

    def get_hierarchy_tree(self) -> List[Dict[str, Any]]:
        """Return the complete nested clause hierarchy tree from Level 1 down to Level 4."""
        all_clauses = self.db.query(ISOClause).order_by(ISOClause.clause_number).all()
        if not all_clauses:
            self.sync_iso_knowledge_base()
            all_clauses = self.db.query(ISOClause).order_by(ISOClause.clause_number).all()

        nodes: Dict[str, Dict[str, Any]] = {}
        for c in all_clauses:
            nodes[c.clause_number] = {
                "clause_id": c.id,
                "clause_number": c.clause_number,
                "parent_clause_number": c.parent_clause_number,
                "level": c.level,
                "title": c.title,
                "category": c.category,
                "page_start": c.page_start,
                "page_end": c.page_end,
                "requires_procedure": c.requires_documented_procedure,
                "requires_record": c.requires_record,
                "is_normative": c.is_normative,
                "children": [],
            }

        tree: List[Dict[str, Any]] = []
        for c_num, node in nodes.items():
            parent_num = node["parent_clause_number"]
            if parent_num and parent_num in nodes:
                nodes[parent_num]["children"].append(node)
            else:
                tree.append(node)

        # Sort top-level clauses numerically (1, 2, 3, 4, 5, 6, 7, 8)
        def clause_sort_key(node):
            parts = [int(p) for p in node["clause_number"].split(".") if p.isdigit()]
            return parts

        tree.sort(key=clause_sort_key)
        for node in nodes.values():
            node["children"].sort(key=clause_sort_key)

        return tree
