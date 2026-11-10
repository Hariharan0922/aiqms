"""ISO 13485:2016 Machine Learning API Router.

Exposes RESTful endpoints for:
1. Real-time ISO clause prediction and classification
2. ML-driven compliance auditing & gap analysis
3. Model training, evaluation metrics, and lifecycle management
4. Instruction fine-tuning (SFT) dataset export for LLMs
"""

import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_actor
from app.db.session import get_db
from app.services.compliance.iso_ml_model import (
    ISO13485MLModel,
    MODEL_FILE_PATH,
    SFT_DATASET_PATH,
)

ml_compliance_router = APIRouter()

# Global cached ML model instance
_model_instance: Optional[ISO13485MLModel] = None


def get_ml_model(db: Session = Depends(get_db)) -> ISO13485MLModel:
    global _model_instance
    if _model_instance is None:
        _model_instance = ISO13485MLModel(db=db)
        if not _model_instance.load():
            _model_instance.train(db=db)
    return _model_instance


class ISOMLPredictRequest(BaseModel):
    text: str = Field(..., min_length=2, max_length=15000, description="QMS document excerpt, SOP text, or procedure clause")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of top clause predictions to return")


class ISOMLAuditRequest(BaseModel):
    text: str = Field(..., min_length=5, max_length=25000, description="Procedure or policy text to audit for ISO 13485 compliance")
    target_clause: Optional[str] = Field(None, description="Optional target clause number (e.g. '7.5.6'). If omitted, the top predicted clause is used.")


class ISOMLTrainRequest(BaseModel):
    force_retrain: bool = Field(default=False, description="Force retrain and update saved model artifact")


class ISOMLVerifyAndGenerateRequest(BaseModel):
    summary: str = Field(..., min_length=2, max_length=15000, description="User given input or topic summary to verify and enhance")
    template_id: Optional[str] = Field(default="sop", description="Target QMS document template ID (e.g. sop, capa, dmr, complaint)")
    provider: Optional[str] = Field(default="nvidia", description="External cloud API provider: 'nvidia' (NVIDIA NIM) or 'openrouter'")
    organization_name: Optional[str] = Field(default="Apex Medical Technologies Ltd.", description="Organization name")


@ml_compliance_router.post("/compliance/ml/verify-and-generate")
async def verify_and_generate_endpoint(
    body: ISOMLVerifyAndGenerateRequest,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Executes the full 4-stage pipeline:
    1. ISO 13485 ML Model Input Verification & Comparison
    2. Online Resources & Industrial Standards Research (DuckDuckGo + quantitative specs)
    3. External Cloud API (NVIDIA NIM Hosted Inference / OpenRouter) Structured Generation
    4. Schema-Validated Quality Packaging & Verification Scorecard
    """
    from app.services.enhancement_service import ContentEnhancementService
    t0 = time.perf_counter()
    service = ContentEnhancementService(db=db)
    try:
        enhanced = await service.enhance_topic_summary(
            template_id=body.template_id or "sop",
            summary=body.summary,
            organization_name=body.organization_name,
            provider_name=body.provider or "nvidia",
        )
        total_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "status": "success",
            "pipeline_stages": [
                "1. ISO 13485 ML Model Input Verification & Comparison",
                "2. Online Resources & Industrial Standards Research",
                "3. External Cloud API (NVIDIA NIM) Structured Generation",
                "4. Schema-Validated Quality Packaging",
            ],
            "total_latency_ms": total_latency_ms,
            "ml_verification": enhanced.get("ml_verification"),
            "online_resources": enhanced.get("online_resources"),
            "external_api": {
                "provider": enhanced.get("provider"),
                "model_id": enhanced.get("model_id"),
            },
            "structured_content": {
                "title": enhanced.get("title"),
                "answers": enhanced.get("answers"),
                "applicability": enhanced.get("applicability"),
                "enhancement_summary": enhanced.get("enhancement_summary"),
                "relevant_iso_clauses": enhanced.get("relevant_iso_clauses"),
            },
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Pipeline error: {str(exc)}")


@ml_compliance_router.post("/compliance/ml/predict-clause")
def predict_clause_endpoint(
    body: ISOMLPredictRequest,
    model: ISO13485MLModel = Depends(get_ml_model),
    actor: dict = Depends(get_actor),
):
    """Predicts relevant ISO 13485:2016 clauses from procedure text using calibrated ML classifier."""
    t0 = time.perf_counter()
    try:
        predictions = model.predict_clause(body.text, top_k=body.top_k)
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "status": "success",
            "model_version": model.version,
            "inference_latency_ms": latency_ms,
            "input_character_count": len(body.text),
            "predictions_count": len(predictions),
            "top_match": predictions[0] if predictions else None,
            "predictions": predictions,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ML Clause Prediction failed: {str(exc)}")


@ml_compliance_router.post("/compliance/ml/audit")
def audit_text_endpoint(
    body: ISOMLAuditRequest,
    model: ISO13485MLModel = Depends(get_ml_model),
    actor: dict = Depends(get_actor),
):
    """Conducts automated ML gap analysis and compliance assessment against ISO 13485:2016."""
    t0 = time.perf_counter()
    try:
        result = model.audit_text(body.text, target_clause_number=body.target_clause)
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        result["inference_latency_ms"] = latency_ms
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ML Compliance Audit failed: {str(exc)}")


@ml_compliance_router.get("/compliance/ml/model-info")
def get_model_info_endpoint(
    model: ISO13485MLModel = Depends(get_ml_model),
    actor: dict = Depends(get_actor),
):
    """Returns telemetry, accuracy metrics, and class distribution of the ISO 13485 ML model."""
    return {
        "model_name": "ISO 13485:2016 Regulatory Classifier & Audit ML Pipeline",
        "standard": "ISO 13485:2016(E)",
        "version": model.version,
        "is_loaded": model.is_loaded,
        "trained_at": model.trained_at,
        "metrics": model.metrics,
        "artifact_path": str(MODEL_FILE_PATH),
        "total_classes": len(model.clause_metadata),
        "classes_sample": list(model.clause_metadata.keys())[:15],
    }


@ml_compliance_router.post("/compliance/ml/train")
def train_model_endpoint(
    body: ISOMLTrainRequest,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Trains/retrains the ISO 13485 ML model from authoritative database clauses and domain scenarios."""
    global _model_instance
    t0 = time.perf_counter()
    model = ISO13485MLModel(db=db)
    metrics = model.train(db=db)
    _model_instance = model
    duration_s = round(time.perf_counter() - t0, 2)

    return {
        "status": "success",
        "message": "ISO 13485:2016 ML Model trained and saved successfully.",
        "training_duration_seconds": duration_s,
        "metrics": metrics,
    }


@ml_compliance_router.get("/compliance/ml/dataset/sft")
def get_sft_dataset_info(
    limit: int = Query(default=10, ge=1, le=100),
    actor: dict = Depends(get_actor),
):
    """Returns sample records from the generated ISO 13485 LLM fine-tuning dataset."""
    if not SFT_DATASET_PATH.exists():
        raise HTTPException(status_code=404, detail="SFT dataset not yet generated. Train the model first.")

    import json
    records = []
    total_count = 0
    with open(SFT_DATASET_PATH, "r", encoding="utf-8") as f:
        for line in f:
            total_count += 1
            if len(records) < limit:
                records.append(json.loads(line))

    return {
        "standard": "ISO 13485:2016",
        "dataset_path": str(SFT_DATASET_PATH),
        "total_sft_records": total_count,
        "sample_records": records,
    }


@ml_compliance_router.get("/compliance/ml/export/sft-file")
def download_sft_file(actor: dict = Depends(get_actor)):
    """Downloads the full ISO 13485 JSONL dataset for fine-tuning LLMs (Llama, Mistral, Qwen, etc.)."""
    if not SFT_DATASET_PATH.exists():
        raise HTTPException(status_code=404, detail="SFT dataset not found. Train the model first.")
    return FileResponse(
        path=SFT_DATASET_PATH,
        filename="iso_13485_sft_dataset.jsonl",
        media_type="application/jsonlines",
    )
