import logging
from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)


def run_migrations(engine):
    """Ensure non-breaking schema additions are migrated across SQLite and PostgreSQL."""
    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())

        # Check ingested_documents
        if "ingested_documents" in existing_tables:
            columns = {c["name"] for c in inspector.get_columns("ingested_documents")}
            with engine.begin() as conn:
                if "vector_status" not in columns:
                    conn.execute(text("ALTER TABLE ingested_documents ADD COLUMN vector_status VARCHAR(30) DEFAULT 'unindexed'"))
                    logger.info("Migrated: added vector_status to ingested_documents")
                if "vector_indexed_at" not in columns:
                    conn.execute(text("ALTER TABLE ingested_documents ADD COLUMN vector_indexed_at DATETIME"))
                    logger.info("Migrated: added vector_indexed_at to ingested_documents")

        # Check ingested_chunks
        if "ingested_chunks" in existing_tables:
            columns = {c["name"] for c in inspector.get_columns("ingested_chunks")}
            with engine.begin() as conn:
                if "embedding_status" not in columns:
                    conn.execute(text("ALTER TABLE ingested_chunks ADD COLUMN embedding_status VARCHAR(30) DEFAULT 'pending'"))
                    logger.info("Migrated: added embedding_status to ingested_chunks")
                if "embedding_model" not in columns:
                    conn.execute(text("ALTER TABLE ingested_chunks ADD COLUMN embedding_model VARCHAR(50) DEFAULT 'nomic-embed-text'"))
                    logger.info("Migrated: added embedding_model to ingested_chunks")
                if "embedded_at" not in columns:
                    conn.execute(text("ALTER TABLE ingested_chunks ADD COLUMN embedded_at DATETIME"))
                    logger.info("Migrated: added embedded_at to ingested_chunks")
                if "vector_id" not in columns:
                    conn.execute(text("ALTER TABLE ingested_chunks ADD COLUMN vector_id VARCHAR(50)"))
                    logger.info("Migrated: added vector_id to ingested_chunks")
                if "content_hash" not in columns:
                    conn.execute(text("ALTER TABLE ingested_chunks ADD COLUMN content_hash VARCHAR(64)"))
                    logger.info("Migrated: added content_hash to ingested_chunks")
                if "embedding_error" not in columns:
                    conn.execute(text("ALTER TABLE ingested_chunks ADD COLUMN embedding_error TEXT"))
                    logger.info("Migrated: added embedding_error to ingested_chunks")

        # Check iso_clauses
        if "iso_clauses" in existing_tables:
            columns = {c["name"] for c in inspector.get_columns("iso_clauses")}
            with engine.begin() as conn:
                if "level" not in columns:
                    conn.execute(text("ALTER TABLE iso_clauses ADD COLUMN level INTEGER DEFAULT 1"))
                    logger.info("Migrated: added level to iso_clauses")
                if "page_start" not in columns:
                    conn.execute(text("ALTER TABLE iso_clauses ADD COLUMN page_start INTEGER"))
                    logger.info("Migrated: added page_start to iso_clauses")
                if "page_end" not in columns:
                    conn.execute(text("ALTER TABLE iso_clauses ADD COLUMN page_end INTEGER"))
                    logger.info("Migrated: added page_end to iso_clauses")
                if "subclauses_count" not in columns:
                    conn.execute(text("ALTER TABLE iso_clauses ADD COLUMN subclauses_count INTEGER DEFAULT 0"))
                    logger.info("Migrated: added subclauses_count to iso_clauses")
                if "content_hash" not in columns:
                    conn.execute(text("ALTER TABLE iso_clauses ADD COLUMN content_hash VARCHAR(64)"))
                    logger.info("Migrated: added content_hash to iso_clauses")
                if "vector_id" not in columns:
                    conn.execute(text("ALTER TABLE iso_clauses ADD COLUMN vector_id VARCHAR(64)"))
                    logger.info("Migrated: added vector_id to iso_clauses")
                if "embedded_at" not in columns:
                    conn.execute(text("ALTER TABLE iso_clauses ADD COLUMN embedded_at DATETIME"))
                    logger.info("Migrated: added embedded_at to iso_clauses")
                if "normative_text" not in columns:
                    conn.execute(text("ALTER TABLE iso_clauses ADD COLUMN normative_text TEXT"))
                    logger.info("Migrated: added normative_text to iso_clauses")
                if "explanatory_notes" not in columns:
                    conn.execute(text("ALTER TABLE iso_clauses ADD COLUMN explanatory_notes TEXT"))
                    logger.info("Migrated: added explanatory_notes to iso_clauses")
                if "is_normative" not in columns:
                    conn.execute(text("ALTER TABLE iso_clauses ADD COLUMN is_normative BOOLEAN DEFAULT 1"))
                    logger.info("Migrated: added is_normative to iso_clauses")

        # Check compliance_traceability_runs
        if "compliance_traceability_runs" in existing_tables:
            columns = {c["name"] for c in inspector.get_columns("compliance_traceability_runs")}
            with engine.begin() as conn:
                for col, sql_type in [
                    ("not_mapped_count", "INTEGER DEFAULT 0"),
                    ("evidence_identified_count", "INTEGER DEFAULT 0"),
                    ("pending_review_count", "INTEGER DEFAULT 0"),
                    ("verified_count", "INTEGER DEFAULT 0"),
                    ("insufficient_evidence_count", "INTEGER DEFAULT 0"),
                ]:
                    if col not in columns:
                        conn.execute(text(f"ALTER TABLE compliance_traceability_runs ADD COLUMN {col} {sql_type}"))

        # Check compliance_traceability_items
        if "compliance_traceability_items" in existing_tables:
            columns = {c["name"] for c in inspector.get_columns("compliance_traceability_items")}
            with engine.begin() as conn:
                for col, sql_type in [
                    ("document_id", "VARCHAR(40)"),
                    ("document_number", "VARCHAR(100)"),
                    ("document_revision", "VARCHAR(50)"),
                    ("section_number", "VARCHAR(50)"),
                    ("section_title", "VARCHAR(300)"),
                    ("page_start", "INTEGER"),
                    ("page_end", "INTEGER"),
                    ("evidence_excerpt", "TEXT"),
                    ("mapping_status", "VARCHAR(50) DEFAULT 'not_mapped'"),
                    ("mapping_confidence", "FLOAT DEFAULT 0.0"),
                    ("rules_validation_status", "VARCHAR(50) DEFAULT 'unvalidated'"),
                    ("rules_findings", "JSON"),
                    ("reviewed_by", "VARCHAR(240)"),
                    ("reviewed_at", "DATETIME"),
                    ("reviewer_decision", "VARCHAR(30)"),
                    ("reviewer_comment", "TEXT"),
                    ("na_justification", "TEXT"),
                    ("audit_trail", "JSON"),
                ]:
                    if col not in columns:
                        conn.execute(text(f"ALTER TABLE compliance_traceability_items ADD COLUMN {col} {sql_type}"))
    except Exception as exc:
        logger.warning("Database migration check encountered exception: %s", exc)
