import urllib.request
import json
import ssl

BASE_URL = "http://127.0.0.1:8000/api/v1"
DOC_ID = "e5ca8744-3d75-4686-8d83-6d2e7c44b18f"

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

def run():
    print(f"=== 1. VERIFYING REQUIREMENT REFERENCES AS ADMIN ===")
    req_updates = {
        "CAPA-INTAKE": {
            "source_edition": "ISO 13485:2016",
            "source_reference": "Clause 8.5.2 & 8.5.3",
            "summary": "Documented procedure to identify and intake nonconformities, customer complaints, and audit findings.",
            "verification_status": "verified",
            "verification_note": "Verified against ISO 13485:2016 normative requirements for nonconformity intake."
        },
        "CAPA-ROOT-CAUSE": {
            "source_edition": "ISO 13485:2016",
            "source_reference": "Clause 8.5.2.b",
            "summary": "Investigation procedure to determine the root cause of nonconformities and assess systemic impact.",
            "verification_status": "verified",
            "verification_note": "Verified root cause investigation methodology."
        },
        "CAPA-EFFECTIVENESS": {
            "source_edition": "ISO 13485:2016",
            "source_reference": "Clause 8.5.2.d",
            "summary": "Mandatory effectiveness verification to ensure corrective action prevents recurrence without adverse impact.",
            "verification_status": "verified",
            "verification_note": "Verified effectiveness review requirement."
        },
        "CAPA-RECORDS": {
            "source_edition": "ISO 13485:2016",
            "source_reference": "Clause 8.5.2 & 4.2.5",
            "summary": "Retention of records documenting investigation findings, actions implemented, and effectiveness evidence.",
            "verification_status": "verified",
            "verification_note": "Verified record control conformity."
        }
    }

    for code, payload in req_updates.items():
        res = api_call(f"/requirements/{code}", method="PATCH", data=payload, role="admin", email="admin@example.local")
        print(f"Verified requirement {code}: status={res.get('verification_status')}")

    print("\n=== 2. UPDATING ANSWERS AND APPLICABILITY AS AUTHOR ===")
    answers_payload = {
        "answers": {
            "organization_name": "MedTech Quality Solutions Ltd.",
            "capa_scope": "This procedure applies to all commercial medical devices, manufacturing processes, customer complaints, audit nonconformities, and supplier quality issues across all facilities.",
            "containment_process": "Immediate quarantine of suspect nonconforming materials, batch hold notifications, segregation in designated secure areas, and preliminary risk assessment within 24 hours.",
            "root_cause_method": "Structured 5-Why analysis, Fishbone (Ishikawa) diagramming, failure mode effect analysis (FMEA), and fault tree evaluations led by cross-functional investigation teams.",
            "action_approval": "Quality Assurance Director and Accountable Engineering Process Owner.",
            "effectiveness_check": "Statistical evaluation of subsequent production batches over a 90-day post-implementation monitoring window with zero recurrence of identical root cause failure modes.",
            "escalation": "Immediate escalation to Executive Management and Regulatory Affairs if patient safety risks or mandatory vigilance reporting triggers are identified.",
            "record_owner": "QA Compliance Document Control Manager."
        },
        "applicability": {
            "CAPA-INTAKE": {"status": "applicable", "rationale": "Mandatory intake protocol for nonconformities and complaints per ISO 13485:2016 Clause 8.5.2."},
            "CAPA-ROOT-CAUSE": {"status": "applicable", "rationale": "Mandatory investigation and root cause determination per ISO 13485:2016 Clause 8.5.2.b."},
            "CAPA-EFFECTIVENESS": {"status": "applicable", "rationale": "Mandatory verification of effectiveness prior to CAPA closure per ISO 13485:2016 Clause 8.5.2.d."},
            "CAPA-RECORDS": {"status": "applicable", "rationale": "Mandatory maintenance of investigation and action records per ISO 13485:2016 Clause 8.5.2 & 4.2.5."}
        }
    }
    doc_updated = api_call(f"/documents/{DOC_ID}/answers", method="PATCH", data=answers_payload, role="author")
    print(f"Answers updated for doc {DOC_ID}")

    print("\n=== 3. RUNNING DETERMINISTIC VALIDATION ===")
    val_res = api_call(f"/documents/{DOC_ID}/validate", method="POST", role="author")
    print("Validation passed:", val_res.get("passed"))
    blockers = [f for f in val_res.get("findings", []) if f.get("blocks_generation")]
    print(f"Blockers count: {len(blockers)}")

    print("\n=== 4. GENERATING DRAFT (OFFLINE DETERMINISTIC - BYPASSING LLM) ===")
    gen_res = api_call(f"/documents/{DOC_ID}/generate", method="POST", data={"provider": "offline"}, role="author")
    v = gen_res.get("current_version", {})
    print(f"Draft generated! Status={v.get('status')} | Provider={v.get('provider')} | Revision={v.get('revision')}")
    sections = v.get("content", {}).get("sections", [])
    print(f"Sections generated ({len(sections)}):")
    for s in sections:
        print(f"  - [{s.get('section_id')}] {s.get('title')}")

    print("\n=== 5. SUBMITTING FOR INDEPENDENT REVIEW ===")
    sub_res = api_call(f"/documents/{DOC_ID}/submit-review", method="POST", data={}, role="author", email="author@example.local")
    print("Document status after submit:", sub_res.get("current_version", {}).get("status"))

    print("\n=== 6. REVIEWING DRAFT (INDEPENDENT REVIEWER) ===")
    review_res = api_call(
        f"/documents/{DOC_ID}/review",
        method="POST",
        data={
            "decision": "accept",
            "comments": "CAPA investigation methodology, containment controls, and 90-day effectiveness checks verified against ISO 13485:2016 Section 8.5.2."
        },
        role="reviewer",
        email="reviewer@example.local"
    )
    print("Document status after review:", review_res.get("current_version", {}).get("status"))

    print("\n=== 7. FORMAL APPROVAL AND RELEASE (APPROVER) ===")
    appr_res = api_call(
        f"/documents/{DOC_ID}/approve",
        method="POST",
        data={
            "decision": "approve",
            "comments": "Formally approved and authorized for release as Revision 1."
        },
        role="approver",
        email="approver@example.local"
    )
    released_version = appr_res.get("current_version", {})
    print(f"RELEASE SUCCESS! Document Status={released_version.get('status')} | Revision={released_version.get('revision')}")

    print("\n=== 8. EXPORTING RELEASED CONTROLLED DOCUMENT ===")
    docx_bytes = api_call(f"/documents/{DOC_ID}/export?format=docx", method="GET", role="author")
    print(f"DOCX export downloaded: {len(docx_bytes):,} bytes")

    pdf_bytes = api_call(f"/documents/{DOC_ID}/export?format=pdf", method="GET", role="author")
    print(f"PDF export downloaded: {len(pdf_bytes):,} bytes")

    print("\n=== COMPLETE WORKFLOW COMPLETED SUCCESSFULLY VIA API ===")

if __name__ == "__main__":
    run()
