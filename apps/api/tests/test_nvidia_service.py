import json
import pytest
from unittest.mock import patch, MagicMock
from app.services.nvidia_service import (
    NvidiaService,
    NvidiaAuthenticationError,
    NvidiaTimeoutError,
    NvidiaServiceError,
)
from app.schemas.generated_document import GeneratedDocument


def test_nvidia_service_unconfigured():
    svc = NvidiaService(api_key="")
    assert not svc.is_configured
    with pytest.raises(NvidiaAuthenticationError, match="NVIDIA_API_KEY is not configured"):
        svc._sync_http_post("chat/completions", {})


def test_nvidia_service_connectivity_mock_success():
    svc = NvidiaService(api_key="nvapi-mock-test-key")
    mock_resp = {
        "id": "chatcmpl-test-connectivity",
        "choices": [{"message": {"content": '{"status": "OK"}'}}],
        "usage": {"total_tokens": 10},
    }
    with patch.object(svc, "_sync_http_post", return_value=mock_resp):
        res = svc.test_connectivity()
        assert res["success"] is True
        assert res["configured"] is True
        assert res["response_time_ms"] is not None
        assert res["raw_response"] == '{"status": "OK"}'


def test_nvidia_service_connectivity_mock_error():
    svc = NvidiaService(api_key="nvapi-mock-test-key")
    with patch.object(svc, "_sync_http_post", side_effect=NvidiaServiceError("Connection timed out")):
        res = svc.test_connectivity()
        assert res["success"] is False
        assert "Connection timed out" in res["error"]


def test_nvidia_service_json_extraction():
    assert NvidiaService.extract_json('{"key": "value"}') == {"key": "value"}
    assert NvidiaService.extract_json('```json\n{"key": "value"}\n```') == {"key": "value"}
    assert NvidiaService.extract_json('Here is the output:\n```json\n{"a": [1, 2, 3]}\n```\nHope it helps!') == {"a": [1, 2, 3]}


def test_nvidia_service_generate_document_content():
    svc = NvidiaService(api_key="nvapi-mock-test-key")
    mock_doc_json = {
        "title": "Cleanroom Monitoring Procedure",
        "document_type": "Standard Operating Procedure",
        "purpose": "Control environmental particulate contamination.",
        "scope": "Applies to ISO Class 7 cleanroom suites.",
        "sections": [
            {
                "section_id": "purpose",
                "title": "Purpose",
                "content": "Detailed purpose.",
                "requirement_refs": ["QMS-DOC-CONTROL"],
                "unresolved_items": [],
            },
            {
                "section_id": "scope",
                "title": "Scope",
                "content": "Detailed scope.",
                "requirement_refs": ["QMS-RECORDS"],
                "unresolved_items": [],
            },
        ],
    }
    mock_resp = {
        "choices": [{"message": {"content": json.dumps(mock_doc_json)}}]
    }
    with patch.object(svc, "_sync_http_post", return_value=mock_resp):
        doc = svc.generate_document_content("system", "prompt", {}, expected_sections=["purpose", "scope"])
        assert isinstance(doc, GeneratedDocument)
        assert doc.title == "Cleanroom Monitoring Procedure"
        assert len(doc.sections) == 2
        assert doc.sections[0].section_id == "purpose"


def test_nvidia_service_regenerate_section():
    svc = NvidiaService(api_key="nvapi-mock-test-key")
    mock_sec_json = {
        "section_id": "procedure",
        "title": "Procedure",
        "content": "Updated particulate sampling method steps.",
        "requirement_refs": ["QMS-RECORDS"],
        "unresolved_items": [],
    }
    mock_resp = {
        "choices": [{"message": {"content": json.dumps(mock_sec_json)}}]
    }
    with patch.object(svc, "_sync_http_post", return_value=mock_resp):
        sec = svc.regenerate_section(
            section_id="procedure",
            section_title="Procedure",
            template={"name": "SOP"},
            answers={},
            current_content={},
            user_guidance="Add optical particle counting steps",
        )
        assert sec.section_id == "procedure"
        assert sec.content == "Updated particulate sampling method steps."
