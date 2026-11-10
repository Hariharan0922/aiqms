from fastapi import Header, HTTPException
from app.core.config import settings


def get_actor(
    x_actor_email: str | None = Header(default=None),
    x_actor_role: str | None = Header(default=None),
    x_organization_id: str | None = Header(default=None),
):
    if not settings.dev_auth_enabled:
        raise HTTPException(status_code=401, detail="Production identity is not configured. Integrate and enable your OIDC identity provider before deployment.")
    role = (x_actor_role or "author").lower()
    if role not in {"author", "reviewer", "approver", "admin"}:
        raise HTTPException(status_code=403, detail="Unknown development role.")
    email = x_actor_email or f"demo.{role}@example.local"
    return {"email": email, "role": role, "organization_id": x_organization_id or "demo-org"}
