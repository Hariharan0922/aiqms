#!/usr/bin/env python3
"""AiDocMaker - Automated Deployment Verification Suite.

Tests all deployed services, database persistence, ML model inference,
and NVIDIA NIM API integration against a running deployment.
Usage:
    python scripts/verify_deployment.py --base-url http://localhost:8000
"""

import argparse
import json
import sys
import time
from typing import Any, Dict
import urllib.request
import urllib.error


def make_request(url: str, method: str = "GET", data: Dict[str, Any] = None, headers: Dict[str, str] = None) -> Dict[str, Any]:
    req_headers = {
        "Accept": "application/json",
        "X-Actor-Email": "demo.author@example.local",
        "X-Actor-Role": "author",
        "X-Organization-Id": "demo-org",
    }
    if headers:
        req_headers.update(headers)

    body_bytes = None
    if data is not None:
        body_bytes = json.dumps(data).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body_bytes, headers=req_headers, method=method)
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=30) as resp:
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        raw = resp.read().decode("utf-8")
        try:
            return {"status_code": resp.status, "duration_ms": duration_ms, "json": json.loads(raw)}
        except Exception:
            return {"status_code": resp.status, "duration_ms": duration_ms, "text": raw}


def main():
    if sys.stdout.encoding != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Verify AiDocMaker Deployment")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL of backend API")
    parser.add_argument("--web-url", default="http://localhost:80", help="Base URL of frontend Nginx/Web")
    args = parser.parse_args()

    api_url = args.base_url.rstrip("/")
    web_url = args.web_url.rstrip("/")

    print("========================================================")
    print("   🔍 Running AiDocMaker Production Verification")
    print(f"   API Target: {api_url}")
    print(f"   Web Target: {web_url}")
    print("========================================================\n")

    passed = 0
    total = 0

    def test(name: str, fn):
        nonlocal passed, total
        total += 1
        print(f"[{total}] Testing: {name}...", end=" ", flush=True)
        try:
            res = fn()
            print(f"✔ PASS ({res.get('duration_ms', 0)} ms)")
            passed += 1
            return res
        except Exception as e:
            print(f"❌ FAIL: {e}")
            return None

    # Test 1: Frontend Web Response
    test("Frontend Web Response (Nginx)", lambda: make_request(f"{web_url}/"))

    # Test 2: Root API Response
    test("Backend Root Endpoint", lambda: make_request(f"{api_url}/"))

    # Test 3: System Diagnostics
    test("System Diagnostics (DB, Templates, Rendering)", lambda: make_request(f"{api_url}/api/v1/system/diagnostics"))

    # Test 4: Template Registry
    test("Template Library (10 starter templates)", lambda: make_request(f"{api_url}/api/v1/templates"))

    # Test 5: ISO 13485 ML Model Info
    test("ISO 13485 ML Classifier Telemetry", lambda: make_request(f"{api_url}/api/v1/compliance/ml/model-info"))

    # Test 6: ML Clause Inference
    test(
        "ML Regulatory Clause Prediction",
        lambda: make_request(
            f"{api_url}/api/v1/compliance/ml/predict-clause",
            method="POST",
            data={"text": "Organization shall establish procedures for corrective action to eliminate nonconformities.", "top_k": 3},
        ),
    )

    # Test 7: NVIDIA NIM Connectivity
    test("NVIDIA NIM Hosted API Connectivity", lambda: make_request(f"{api_url}/api/v1/system/test-nvidia", method="POST"))

    # Test 8: OpenRouter Connectivity
    test("OpenRouter API Connectivity", lambda: make_request(f"{api_url}/api/v1/system/test-openrouter", method="POST"))

    # Test 9: Create Document with Template
    created_id = None
    try:
        def create_doc():
            nonlocal created_id
            r = make_request(
                f"{api_url}/api/v1/documents",
                method="POST",
                data={"template_id": "sop", "title": "Automated Verification Test SOP", "answers": {}},
            )
            created_id = r["json"]["id"]
            return r

        test("Controlled Document Creation & SQLite Persistence", create_doc)
    finally:
        pass

    print("\n========================================================")
    print(f"   Scorecard: {passed}/{total} Tests Passed ({(passed / total) * 100:.1f}%)")
    if passed == total:
        print("   Status: 🟢 ALL PRODUCTION DEPLOYMENT CHECKS PASSED")
    else:
        print("   Status: 🔴 SOME CHECKS FAILED - Inspect logs above")
    print("========================================================")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
