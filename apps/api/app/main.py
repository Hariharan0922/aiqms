import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.session import Base, engine, SessionLocal
from app.db.migrations import run_migrations
from app.models import *  # noqa: F401,F403 - import registers ORM tables
from app.models.entities import RequirementReference
from app.templates.registry import REQUIREMENTS
from app.api.v1.router import router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    os.makedirs("data/models", exist_ok=True)
    os.makedirs("data/evidence", exist_ok=True)
    os.makedirs("data/exports", exist_ok=True)
    os.makedirs("data/ingested", exist_ok=True)
    Base.metadata.create_all(bind=engine)
    run_migrations(engine)
    db = SessionLocal()
    try:
        for code, item in REQUIREMENTS.items():
            if not db.query(RequirementReference).filter_by(code=code).first():
                db.add(RequirementReference(**item))
        db.commit()
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Rules-first AI-assisted QMS documentation workflow. Generated drafts require qualified human review.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/")
def root():
    return {"name": settings.app_name, "version": "0.1.0", "docs": "/docs", "api": "/api/v1"}
