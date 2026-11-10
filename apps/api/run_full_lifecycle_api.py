import os
import json
import urllib.request

BASE_URL = "http://127.0.0.1:8000/api/v1"

def api_call(endpoint, method="GET", data=None, role="author", email="author@example.local"):
    url = f"{BASE_URL}{endpoint}"
    headers = {
        "x-actor-role": role,
        "x-actor-email": email,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        content_type = resp.headers.get("Content-Type", "")
        if "application/json" in content_type:
            return json.loads(resp.read().decode("utf-8"))
        return resp.read()

def run_lifecycle():
    print("=" * 70)
    print("AIQMS STUDIO: END-TO-END CONTROLLED DOCUMENT LIFECYCLE (OFFLINE/API)")
    print("=" * 70)

    # 1. VERIFY REQUIREMENT MAPPINGS AS ADMIN
    print("\n[STEP 1] Administrator verifies ISO 13485 requirement mappings...")
    req_map = {
        "QMS-DOC-CONTROL": {
            "source_edition": "ISO 13485:2016",
            "source_reference": "Clause 4.2.4 Control of documents",
            "summary": "Mandatory documented procedure to review, approve, update, and re-approve documents prior to issue.",
            "verification_status": "verified",
            "verification_note": "Verified against ISO 13485:2016 Clause 4.2.4 by Lead QA Auditor."
        },
        "QMS-RECORDS": {
            "source_edition": "ISO 13485:2016",
            "source_reference": "Clause 4.2.5 Control of records",
            "summary": "Establish and maintain records to provide evidence of conformity to requirements and QMS operation.",
            "verification_status": "verified",
            "verification_note": "Verified retention and integrity controls per Clause 4.2.5."
        },
        "QMS-RESPONSIBILITY": {
            "source_edition": "ISO 13485:2016",
            "source_reference": "Clause 5.5.1 Responsibility and authority",
            "summary": "Top management shall ensure responsibilities and authorities are defined, documented and communicated.",
            "verification_status": "verified",
            "verification_note": "Verified organizational governance matrix per Clause 5.5.1."
        }
    }
    for code, payload in req_map.items():
        res = api_call(f"/requirements/{code}", method="PATCH", data=payload, role="admin", email="admin@example.local")
        print(f"  [OK] Requirement [{code}] verified: {res.get('source_reference')}")

    # 2. CREATE NEW CONTROLLED DOCUMENT AS AUTHOR
    print("\n[STEP 2] Author creates new Standard Operating Procedure (SOP)...")
    create_payload = {
        "template_id": "sop",
        "title": "SOP: Medical Device Cleanroom Contamination and Environmental Monitoring",
        "answers": {
            "organization_name": "Apex BioDevice Technologies Corp.",
            "process_owner": "Cleanroom Operations & Sterility Assurance Lead",
            "purpose": "Define mandatory contamination control, gowning protocols, viable particle monitoring, and sanitization frequencies for ISO Class 7 cleanrooms.",
            "scope": "Applies to all Class II and Class III device assembly cleanrooms, gowning airlocks, and material pass-through chambers at Facility A.",
            "procedure_steps": "1. Operators inspect airlocks and log differential pressures. 2. Full aseptic gowning donning sequence per WI-CLN-04. 3. Daily active air sampling and surface contact plates. 4. Weekly HEPA laminar flow velocity verification. 5. Immediate quarantine of production line if viable counts exceed alert thresholds.",
            "records": "Form CLN-REC-01 (Daily Environmental Monitoring Log), Form CLN-REC-05 (HEPA Filter Certification), and Form QA-REC-12 (Microbiological Assay Certificate).",
            "reviewer_role": "Sterility Assurance Specialist",
            "approver_role": "Head of Regulatory & Quality Assurance"
        }
    }
    doc = api_call("/documents", method="POST", data=create_payload, role="author", email="author@example.local")
    doc_id = doc["id"]
    doc_num = doc["document_number"]
    print(f"  [OK] Created Document [{doc_num}] (ID: {doc_id})")

    # 3. RECORD APPLICABILITY DECISIONS
    print("\n[STEP 3] Author records requirement applicability decisions...")
    app_payload = {
        "applicability": {
            "QMS-DOC-CONTROL": {"status": "applicable", "rationale": "Governs revision control and distribution of cleanroom procedures."},
            "QMS-RECORDS": {"status": "applicable", "rationale": "Governs retention and archival of environmental monitoring log sheets for 10 years."},
            "QMS-RESPONSIBILITY": {"status": "applicable", "rationale": "Establishes authority for cleanroom halt and quarantine triggers."}
        }
    }
    api_call(f"/documents/{doc_id}/answers", method="PATCH", data=app_payload, role="author", email="author@example.local")
    print("  [OK] Applicability decisions recorded for all 3 mapped ISO requirements.")

    # 4. RUN DETERMINISTIC RULES VALIDATION
    print("\n[STEP 4] Deterministic Rules Engine executes generation gate checks...")
    val_res = api_call(f"/documents/{doc_id}/validate", method="POST", role="author", email="author@example.local")
    findings = val_res.get("findings", [])
    blockers = [f for f in findings if f.get("blocks_generation")]
    print(f"  [OK] Validation Result: passed={val_res.get('passed')} | Blockers={len(blockers)} | Total findings={len(findings)}")

    # 5. GENERATE STRUCTURED DRAFT VIA DETERMINISTIC ENGINE (BYPASSING LLM)
    print("\n[STEP 5] Generating draft using Offline Deterministic Engine (Bypassing LLM)...")
    gen_res = api_call(f"/documents/{doc_id}/generate", method="POST", data={"provider": "offline"}, role="author", email="author@example.local")
    v = gen_res["current_version"]
    sections = v.get("content", {}).get("sections", [])
    print(f"  [OK] Generated draft Revision {v.get('revision')} via provider '{v.get('provider')}'")
    for s in sections:
        print(f"     - [{s['section_id']}] {s['title']}")

    # 6. SUBMIT FOR INDEPENDENT REVIEW
    print("\n[STEP 6] Author submits draft for independent review...")
    sub_res = api_call(f"/documents/{doc_id}/submit-review", method="POST", data={}, role="author", email="author@example.local")
    print(f"  [OK] Workflow State updated: '{sub_res['current_version']['status']}'")

    # 7. INDEPENDENT HUMAN REVIEW (REVIEWER ROLE)
    print("\n[STEP 7] Independent Reviewer evaluates and accepts draft...")
    review_res = api_call(
        f"/documents/{doc_id}/review",
        method="POST",
        data={
            "decision": "accept",
            "comments": "Reviewed cleanroom sanitization intervals, microbiological limits, and gowning controls. Fully conforms to ISO 13485:2016 Clause 6.4.2."
        },
        role="reviewer",
        email="reviewer.cleanroom@example.local"
    )
    print(f"  [OK] Review decision recorded: 'accept' -> New State: '{review_res['current_version']['status']}'")

    # 8. AUTHORIZED APPROVAL & RELEASE (APPROVER ROLE)
    print("\n[STEP 8] Authorized Approver executes release gate and releases Revision 1...")
    appr_res = api_call(
        f"/documents/{doc_id}/approve",
        method="POST",
        data={
            "decision": "approve",
            "comments": "Formally approved for operational release. All requirement mappings verified against standard sources."
        },
        role="approver",
        email="approver.headofqa@example.local"
    )
    released_v = appr_res["current_version"]
    print(f"  [OK] RELEASE COMPLETE! Document State: '{released_v['status']}' | Revision: {released_v['revision']}")

    # 9. EXPORT RELEASED DOCUMENTS
    print("\n[STEP 9] Exporting released controlled document to DOCX and PDF...")
    os.makedirs("data/exports", exist_ok=True)
    
    docx_data = api_call(f"/documents/{doc_id}/export?format=docx", method="GET", role="author")
    docx_path = f"data/exports/{doc_num}.docx"
    with open(docx_path, "wb") as f:
        f.write(docx_data)
    print(f"  [OK] DOCX exported: {docx_path} ({len(docx_data):,} bytes)")

    pdf_data = api_call(f"/documents/{doc_id}/export?format=pdf", method="GET", role="author")
    pdf_path = f"data/exports/{doc_num}.pdf"
    with open(pdf_path, "wb") as f:
        f.write(pdf_data)
    print(f"  [OK] PDF exported: {pdf_path} ({len(pdf_data):,} bytes)")

    # 10. AUDIT TRAIL SUMMARY
    print("\n[STEP 10] Fetching 21 CFR Part 11 compliant audit trail...")
    audit_events = api_call(f"/audit?entity_id={doc_id}&limit=20", method="GET", role="admin", email="admin@example.local")
    print(f"  [OK] Recorded {len(audit_events)} audit events for this document:")
    for ev in audit_events:
        print(f"     - [{ev.get('action')}] by {ev.get('actor_email')} ({ev.get('actor_role')}) at {ev.get('created_at')[:19]}")

    print("\n" + "=" * 70)
    print("SUCCESS: Full QMS Lifecycle executed cleanly via API without LLM dependency!")
    print("=" * 70)

if __name__ == "__main__":
    run_lifecycle()
