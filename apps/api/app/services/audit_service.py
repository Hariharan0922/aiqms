from sqlalchemy.orm import Session
from app.models.entities import AuditEvent


def record_event(db: Session, actor: dict, action: str, entity_type: str, entity_id: str, metadata: dict | None = None):
    db.add(AuditEvent(
        organization_id=actor.get("organization_id", "default"), actor_email=actor["email"], actor_role=actor["role"],
        action=action, entity_type=entity_type, entity_id=entity_id, metadata_json=metadata or {},
    ))
