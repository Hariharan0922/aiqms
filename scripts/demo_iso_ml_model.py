"""Interactive CLI demonstration for the ISO 13485:2016 Machine Learning Model."""

import sys
from pathlib import Path

# Add apps/api to PYTHONPATH
api_path = Path(__file__).resolve().parents[1] / "apps" / "api"
if str(api_path) not in sys.path:
    sys.path.insert(0, str(api_path))

from app.db.session import SessionLocal
from app.services.compliance.iso_ml_model import ISO13485MLModel


def main():
    print("=" * 80)
    print("  ISO 13485:2016 REGULATORY MACHINE LEARNING MODEL DEMO")
    print("=" * 80)

    db = SessionLocal()
    model = ISO13485MLModel(db=db)
    if not model.load():
        print("[*] Model artifact not found. Training from ISO 13485 standard...")
        model.train(db=db)
    else:
        print(f"[*] Loaded ISO 13485:2016 ML Model (v{model.version}, trained: {model.trained_at})")
    db.close()

    test_queries = [
        (
            "Sterilization Validation",
            "Ethylene oxide sterilization cycle validation per ISO 11135. Critical process parameters including gas concentration, humidity, and biological indicators shall be recorded for each lot.",
        ),
        (
            "Medical Device File / DMR",
            "Device Master Record defining specifications, bill of materials, packaging procedures, and acceptance criteria for Model X cardiac catheters.",
        ),
        (
            "Customer Complaints",
            "Documented procedure for timely intake, investigation, and root cause determination of customer complaints and vigilance reporting.",
        ),
        (
            "Equipment Metrology",
            "Calibration program for digital micrometers and force gauges traceable to national standards (NIST). Calibration certificates retained.",
        ),
    ]

    for title, text in test_queries:
        print("\n" + "-" * 80)
        print(f"SCENARIO: {title}")
        print(f"INPUT TEXT: \"{text}\"")
        
        preds = model.predict_clause(text, top_k=3)
        top = preds[0]
        print(f"\n[+] TOP ML PREDICTION: Clause {top['clause_number']} - {top['title']}")
        print(f"    Confidence: {top['confidence_percent']} (ML Prob: {top['ml_probability']}, Cosine Sim: {top['semantic_similarity']})")
        print(f"    Category: {top['category']} | PDF Pages: {top['page_start']}-{top['page_end']}")
        print(f"    Documented SOP Required: {'YES' if top['requires_documented_procedure'] else 'NO'}")
        print(f"    Quality Records Required: {'YES' if top['requires_record'] else 'NO'}")

        audit = model.audit_text(text)
        print(f"\n[+] COMPLIANCE AUDIT:")
        print(f"    Verdict: {audit['verdict_label']} (Score: {audit['compliance_score']}%)")
        print(f"    Strengths: {', '.join(audit['strengths'])}")
        print(f"    Gaps: {', '.join(audit['gaps'])}")
        print(f"    Remediation: {', '.join(audit['recommendations'])}")

    print("\n" + "=" * 80)
    print("  DEMO COMPLETE - ML MODEL FULLY OPERATIONAL")
    print("=" * 80)


if __name__ == "__main__":
    main()
