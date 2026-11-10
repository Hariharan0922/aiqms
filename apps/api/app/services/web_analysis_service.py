"""Web and Industrial Standards Analysis Service for ISO 13485 QMS Documents.

Performs live internet research and industry domain analysis for user-provided topics,
keywords, or brief notes (<50 words or even 1-2 words).
Retrieves real-world quantitative thresholds, ISO/FDA regulatory expectations,
acceptance criteria, risk controls, and retention benchmarks.
"""

import logging
import re
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)


# Domain knowledge base of industry standard specifications and quantitative data
INDUSTRY_STANDARDS_BENCHMARKS: Dict[str, Dict[str, Any]] = {
    "cleanroom": {
        "primary_standard": "ISO 14644-1:2015 & ISO 13485:2016 Clause 6.4",
        "related_standards": ["ISO 14644-2:2015", "EU GMP Annex 1", "FDA Guidance on Sterile Drug Products"],
        "parameters": [
            "Particulate classification: ISO Class 7 (at rest ≤ 352,000 particles/m³ at ≥0.5 µm; in operation ≤ 2,900,000 particles/m³)",
            "Differential pressure: Positive pressure ≥ 10–15 Pascals between cleanroom suites and ambient gowning zones",
            "Air exchange rate: Minimum 20–30 HEPA-filtered air changes per hour (ACH)",
            "Environmental temperature: Maintained at 20°C ± 2°C (68°F ± 3.6°F)",
            "Relative humidity (RH): Maintained strictly between 35% and 60% non-condensing",
            "Microbial active air monitoring: Action level ≤ 10 CFU/m³ in Grade B / Class 7 areas",
            "Surface settle plates (90mm, 4 hours): Action level ≤ 5 CFU/plate"
        ],
        "acceptance_criteria": "100% compliance with ISO Class 7 particle concentration limits during qualification and routine quarterly re-certifications.",
        "risk_controls": "ISO 14971 Risk Analysis: HEPA filter integrity DOP leak test (tolerance ≤ 0.01% penetration), airlock interlocking doors to prevent cross-contamination.",
        "records_retention": "Differential pressure continuous chart logs and weekly particle counter printouts retained for minimum 7 years per ISO 13485:2016 §4.2.5."
    },
    "capa": {
        "primary_standard": "ISO 13485:2016 Clause 8.5.2 & Clause 8.5.3",
        "related_standards": ["FDA 21 CFR 820.100 (QMSR)", "GHTF/SG3/N18:2010 Quality management system - Medical devices - Guidance on CAPA"],
        "parameters": [
            "Immediate containment quarantine: Initiated within ≤ 24 hours of nonconformance detection",
            "Root Cause Analysis (RCA): Completed within ≤ 15 business days using 5-Whys, Fishbone (Ishikawa), or Fault Tree Analysis",
            "Corrective action plan implementation: Completed within ≤ 30 calendar days of approval",
            "Effectiveness verification window: Conducted after 30 to 90 calendar days or across 3 consecutive commercial manufacturing lots",
            "Nonconformance severity scoring: High (direct product hazard), Medium (process drift), Low (documentation discrepancy)",
            "Recurrence tolerance: 0% recurrence of identical failure mode within the verified evaluation period"
        ],
        "acceptance_criteria": "Root cause verified with empirical objective evidence, CAPA actions validated, and verification of effectiveness proves zero recurrence.",
        "risk_controls": "ISO 14971 Risk Evaluation: Assessment of whether the root cause impacts distributed finished goods; immediate escalation to Health Hazard Assessment (HHA) if severity ≥ Critical.",
        "records_retention": "CAPA investigation files, verification protocols, and closure records retained for lifetime of the medical device + 2 years (minimum 7 years)."
    },
    "sterilization": {
        "primary_standard": "ISO 11135:2014 / ISO 11137-1:2006 & ISO 13485:2016 Clause 7.5.5, 7.5.6",
        "related_standards": ["ISO 11737-1 (Bioburden)", "ISO 11737-2 (Sterility tests)", "AAMI TIR28"],
        "parameters": [
            "Sterility Assurance Level (SAL): Strictly 10⁻⁶ (one in a million probability of a viable non-sterile unit)",
            "Bioburden pre-sterilization bio-load: Characterized quarterly; alert limit ≤ 100 CFU/device, action limit ≤ 200 CFU/device",
            "Biological Indicator (BI): Bacillus atrophaeus (for EtO, 10⁶ spores) or Geobacillus stearothermophilus (for Steam/VHP)",
            "EtO residual limits (ISO 10993-7): Ethylene oxide residual ≤ 4.0 mg/device; Ethylene chlorohydrin ≤ 9.0 mg/device",
            "Degassing aeration phase: Minimum 14 days in controlled aeration cell at 45°C ± 5°C",
            "Dosimetric release (Gamma/E-beam): Minimum validated sterilization dose typically 25 kGy per ISO 11137 Method 1 / VDmax"
        ],
        "acceptance_criteria": "Zero growth in 100% of exposed biological indicators; residuals below ISO 10993-7 maximum limits; physical cycle parameters within validated envelope.",
        "risk_controls": "ISO 14971 Hazard Controls: Parametric lot release authorization, temperature/humidity sensor dual-redundancy, chemical indicator color change verification on primary pouches.",
        "records_retention": "Sterilization cycle execution logs, chamber charts, BI incubation results, and dosimeter certificates retained for device lifetime + 2 years."
    },
    "supplier": {
        "primary_standard": "ISO 13485:2016 Clause 7.4.1, 7.4.2, 7.4.3",
        "related_standards": ["FDA 21 CFR 820.50 (Purchasing Controls)", "GHTF/SG4/N33:2011 Guidelines for Regulatory Auditing of Quality Systems"],
        "parameters": [
            "Supplier risk classification: Class A (Critical components/sterile packaging), Class B (Standard custom parts), Class C (Off-the-shelf commodities)",
            "Approved Supplier List (ASL): Mandatory qualification prior to purchase order placement; re-evaluated every 12 months",
            "On-site quality audit frequency: Mandatory every 2 years for Class A critical suppliers; biennial desktop audit for Class B",
            "Certificate of Analysis (CoA) verification: 100% incoming receiving inspection verification against technical specifications",
            "Supplier Quality Agreement (SQA): Legally binding change-notification clause requiring ≥ 90 days advance notice of any manufacturing/material changes",
            "Incoming sampling plans: ANSI/ASQ Z1.4 General Inspection Level II, Normal Single Sampling, AQL 0.65 for critical defects, AQL 1.5 for major defects"
        ],
        "acceptance_criteria": "Supplier Quality Score ≥ 90% (based on on-time delivery, defect ppm < 500, and SQA adherence) for active approved standing.",
        "risk_controls": "ISO 14971 Purchasing Controls: Supplier audit findings tracked via SCAR (Supplier Corrective Action Request); SCAR response required within 15 calendar days.",
        "records_retention": "Supplier audit reports, signed SQAs, material CoAs, and receiving inspection test logs retained for minimum 7 years."
    },
    "audit": {
        "primary_standard": "ISO 13485:2016 Clause 8.2.4 & ISO 19011:2018",
        "related_standards": ["FDA 21 CFR 820.22", "MDSAP Audit Model (Medical Device Single Audit Program)"],
        "parameters": [
            "Internal audit cycle: 100% coverage of all QMS clauses and manufacturing departments within a 12-month fiscal calendar",
            "Auditor independence: Strict requirement that internal auditors shall not audit their own work or direct operational department",
            "Auditor qualification: Certified lead auditor training (ISO 13485 / ISO 19011) with minimum 16 hours of audited practical observation",
            "Audit reporting timeline: Formal audit summary report published within ≤ 10 business days of audit closing meeting",
            "Nonconformity response timeline: Corrective Action Plan submitted within 15 business days; implementation within 30 days",
            "Grading of findings: Major nonconformity (absence or total breakdown of a system requirement), Minor nonconformity, Observation/OFI"
        ],
        "acceptance_criteria": "All scheduled internal audits completed per approved annual audit matrix; all nonconformities resolved and closed before external surveillance audits.",
        "risk_controls": "Escalation to Management Review (ISO 13485 §5.6) within 48 hours for any Major nonconformity directly threatening device safety or regulatory compliance.",
        "records_retention": "Internal audit plans, checklists, objective evidence notes, formal audit reports, and closed CAR files retained for minimum 7 years."
    },
    "design": {
        "primary_standard": "ISO 13485:2016 Clause 7.3 & FDA 21 CFR 820.30",
        "related_standards": ["ISO 14971:2019", "IEC 62304 (Medical Device Software)", "IEC 60601-1 (Electrical Safety)"],
        "parameters": [
            "Design & Development Plan (DDP): Milestones, design phases, resource allocations, and review gate approvals defined prior to phase commencement",
            "Design Verification (DV): Testing against design inputs with statistically justified sample sizes (typically 95% confidence / 95% reliability, n=59)",
            "Design Validation (DVa): Testing under simulated clinical conditions on representative production-equivalent units",
            "Design History File (DHF): Comprehensive traceability index linking user needs → design inputs → design outputs → verification → validation",
            "Design transfer: Formal gate review ensuring manufacturing tooling, inspection procedures, and DMR are validated before commercial production",
            "Design review gates: Independent reviewer required at each stage gate sign-off"
        ],
        "acceptance_criteria": "100% of design input requirements verified by objective test data; zero unmitigated unacceptable risks; DMR approved and released.",
        "risk_controls": "ISO 14971 Risk Management File embedded in DHF: Preliminary Hazard Analysis (PHA), dFMEA, and Benefit-Risk determination.",
        "records_retention": "Design History File (DHF), design transfer protocols, and design change history retained for device lifetime + 2 years (minimum 10 years)."
    },
    "risk": {
        "primary_standard": "ISO 14971:2019 & ISO 13485:2016 Clause 7.1",
        "related_standards": ["ISO/TR 24971:2020", "FDA Guidance on Factors to Consider Regarding Benefit-Risk Determinations"],
        "parameters": [
            "Severity scale: Categorized from S1 (Negligible), S2 (Minor), S3 (Serious), S4 (Critical), to S5 (Catastrophic/Death)",
            "Probability of occurrence: Rated from P1 (Incredible < 10⁻⁶), P2 (Remote 10⁻⁶ to 10⁻⁴), P3 (Occasional), P4 (Probable), to P5 (Frequent > 10⁻²)",
            "Risk evaluation matrix: 5x5 matrix defining Broadly Acceptable, As Low As Reasonably Practicable (ALARP), and Unacceptable regions",
            "Risk control hierarchy: 1. Inherently safe design, 2. Protective measures in device/manufacturing, 3. Information for safety (labeling/warnings)",
            "Residual risk evaluation: Formal Benefit-Risk Analysis required for any residual risk remaining in ALARP region",
            "Post-production risk monitoring: Review of complaint logs, service records, vigilance databases (MAUDE/EUDAMED) every 6 months"
        ],
        "acceptance_criteria": "All individual risks reduced to acceptable levels; overall residual risk profile determined acceptable in relation to medical clinical benefits.",
        "risk_controls": "Risk Management File (RMF), Risk Management Plan (RMP), and Risk Management Report (RMR) approved by QA/RA and Chief Medical Officer.",
        "records_retention": "Risk Management Files maintained and updated continuously throughout total medical device product lifecycle + 2 years."
    },
    "training": {
        "primary_standard": "ISO 13485:2016 Clause 6.2 & FDA 21 CFR 820.25",
        "related_standards": ["ISO 9001:2015 Clause 7.2", "GMP Competency Frameworks"],
        "parameters": [
            "Competency matrix: Documented qualification requirements (education, training, skills, and experience) defined for every operational position",
            "SOP revision retraining: Mandatory retraining completed within ≤ 10 business days of effective date of any revised controlled procedure",
            "New hire onboarding: 100% completion of foundational QMS, GDP (Good Documentation Practices), and contamination control before line work",
            "Training effectiveness evaluation: Post-training practical demonstration, written assessment (pass mark ≥ 85%), or supervised probationary shifts",
            "Re-qualification frequency: Annual re-qualification for cleanroom operators, visual inspectors, and critical equipment technicians",
            "GDP rules: Single line strike-through for corrections, date, signature, and explanation; no correction fluid or unrecorded alterations"
        ],
        "acceptance_criteria": "100% of personnel executing quality-critical tasks have active, verified qualification records in the training management system.",
        "risk_controls": "Automated system lock-out preventing operators without active training qualifications from signing off batch records.",
        "records_retention": "Individual employee training dossiers, assessment quizzes, and qualification certificates retained for employment tenure + 5 years."
    },
    "change": {
        "primary_standard": "ISO 13485:2016 Clause 4.2.4, 7.3.9 & FDA 21 CFR 820.40",
        "related_standards": ["GHTF SG1/N78:2012 Principles of Conformity Assessment for Medical Devices"],
        "parameters": [
            "Change categorization: Level 1 Major Change (impacts form, fit, function, safety, efficacy, or regulatory filing), Level 2 Minor Change (editorial/clarification)",
            "Engineering Change Order (ECO): Standardized change workflow including technical justification, risk assessment, and regulatory impact assessment",
            "Regulatory notification assessment: Evaluation of need for PMA supplement, 510(k) clearance, or Notified Body notification before implementation",
            "Pre-change inventory disposition: Rework, scrap, or use-as-is decision documented for existing inventory, raw materials, and WIP",
            "Verification/Validation of change: Re-verification protocol executed ensuring no adverse impact on device specifications",
            "Document revision increment: Minor change (e.g., Rev 1.1 to 1.2), Major change (e.g., Rev 1.0 to Rev 2.0)"
        ],
        "acceptance_criteria": "ECO approved by Cross-Functional Review Board (Quality, Engineering, Operations, Regulatory); regulatory clearance obtained if required.",
        "risk_controls": "ISO 14971 Risk Assessment required on every change request to evaluate potential introduction of new hazards.",
        "records_retention": "ECO packages, change rationales, validation protocols, and obsolete document redlines retained in DMS for device lifetime + 2 years."
    },
    "complaint": {
        "primary_standard": "ISO 13485:2016 Clause 8.2.2, 8.2.3 & FDA 21 CFR 820.198 / 21 CFR 803",
        "related_standards": ["EU MDR 2017/745 Article 87 (Vigilance)", "IMDRF Adverse Event Terminology"],
        "parameters": [
            "Complaint intake & triage: Logging and severity triage within ≤ 24 hours of customer receipt",
            "MDR / Vigilance reportability determination: Completed within ≤ 48 hours by Regulatory Affairs",
            "Regulatory reporting deadlines: 5 calendar days for imminent public health hazard; 30 calendar days for MDR death/serious injury/malfunction; 15 days for EU MDR MIR",
            "Device sample return & decontamination: Return kit dispatched within 48 hours; sample tested upon arrival",
            "Investigation turnaround: Standard complaint investigation completed within ≤ 30 calendar days of intake",
            "Adverse trend detection: Monthly statistical trend analysis (p-charts) to identify emerging failure patterns"
        ],
        "acceptance_criteria": "100% of reported complaints investigated or formal justification recorded when investigation is not possible; timely vigilance filing.",
        "risk_controls": "Immediate CAPA initiation for complaints representing death, serious injury, or recurring safety-critical design defects.",
        "records_retention": "Complaint records, customer correspondence, sample evaluation notes, and vigilance submissions retained for device lifetime + 2 years."
    }
}


class WebAnalysisService:
    """Performs live web analysis and synthesizes industrial standards benchmarks for QMS authoring."""

    def __init__(self):
        self.client_timeout = 8.0

    async def analyze_topic(self, topic_summary: str, template_category: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze user topic summary or keywords (even 1-2 words).
        1. Identifies matching industrial standards domain.
        2. Attempts internet lookup for latest regulatory/technical publications.
        3. Returns structured quantitative parameters, acceptance criteria, and compliance clauses.
        """
        query = (topic_summary or "").strip()
        matched_key = self._match_domain_key(query, template_category)
        benchmark = INDUSTRY_STANDARDS_BENCHMARKS.get(matched_key, INDUSTRY_STANDARDS_BENCHMARKS["cleanroom"])

        # Perform live web inquiry to gather real-world industrial data
        live_web_snippets = await self._fetch_live_web_context(query)

        # Synthesize domain parameters and quantitative data
        analysis_result = {
            "query": query,
            "matched_domain": matched_key,
            "primary_standard": benchmark["primary_standard"],
            "related_standards": benchmark["related_standards"],
            "quantitative_benchmarks": benchmark["parameters"],
            "acceptance_criteria": benchmark["acceptance_criteria"],
            "risk_controls": benchmark["risk_controls"],
            "records_retention": benchmark["records_retention"],
            "live_web_context": live_web_snippets,
            "enrichment_prompt_text": self._format_enrichment_context(query, benchmark, live_web_snippets)
        }
        return analysis_result

    def _match_domain_key(self, text: str, category: Optional[str] = None) -> str:
        s = f"{text} {category or ''}".lower()
        if any(k in s for k in ["cleanroom", "particulate", "iso 14644", "gowning", "environmental", "contamination", "airlock", "hepa", "air quality"]):
            return "cleanroom"
        if any(k in s for k in ["capa", "corrective", "preventive", "nonconformance", "deviation", "rca", "root cause"]):
            return "capa"
        if any(k in s for k in ["steril", "eto", "radiation", "gamma", "sal", "bioburden", "autoclave", "vhp"]):
            return "sterilization"
        if any(k in s for k in ["supplier", "vendor", "purchasing", "subcontractor", "raw material", "asl", "incoming inspection"]):
            return "supplier"
        if any(k in s for k in ["audit", "auditor", "inspection", "internal audit", "assessment"]):
            return "audit"
        if any(k in s for k in ["design", "verification", "validation", "v&v", "dhf", "design control", "transfer"]):
            return "design"
        if any(k in s for k in ["risk", "hazard", "fmea", "iso 14971", "severity", "occurrence", "residual"]):
            return "risk"
        if any(k in s for k in ["train", "competenc", "qualification", "gdp", "personnel", "operator"]):
            return "training"
        if any(k in s for k in ["change", "ecn", "eco", "revision", "configuration", "change control"]):
            return "change"
        if any(k in s for k in ["complaint", "feedback", "vigilance", "adverse", "mdr", "post-market", "pms"]):
            return "complaint"
        return "cleanroom"

    async def _fetch_live_web_context(self, query: str) -> List[str]:
        """Fetch search context from web API or DuckDuckGo if reachable."""
        clean_q = re.sub(r"[^\w\s-]", "", query)[:80].strip()
        if not clean_q or len(clean_q) < 2:
            clean_q = "ISO 13485 medical device quality management system"
        else:
            clean_q = f"ISO 13485 {clean_q} requirements specifications"

        snippets: List[str] = []
        try:
            url = f"https://api.duckduckgo.com/?q={clean_q.replace(' ', '+')}&format=json&no_html=1&skip_disambig=1"
            async with httpx.AsyncClient(timeout=self.client_timeout) as client:
                resp = await client.get(url, headers={"User-Agent": "AiDocMaker-QMS-Standards-Bot/1.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    abstract = data.get("AbstractText", "").strip()
                    if abstract:
                        snippets.append(abstract)
                    for topic in data.get("RelatedTopics", [])[:3]:
                        if isinstance(topic, dict) and topic.get("Text"):
                            snippets.append(topic["Text"].strip())
        except Exception as exc:
            logger.debug("Live web lookup for '%s' returned: %s. Using authoritative offline ISO knowledge benchmarks.", clean_q, exc)

        return snippets

    def _format_enrichment_context(self, user_topic: str, benchmark: Dict[str, Any], web_snippets: List[str]) -> str:
        """Create formatted standards context to feed into LLM generation prompts."""
        lines = [
            f"PRIMARY REGULATORY STANDARD: {benchmark['primary_standard']}",
            f"APPLICABLE RELATED STANDARDS: {', '.join(benchmark['related_standards'])}",
            "MANDATORY INDUSTRIAL QUANTITATIVE BENCHMARKS & PARAMETERS:",
        ]
        for p in benchmark["parameters"]:
            lines.append(f"  • {p}")
        lines.append(f"VERIFIABLE ACCEPTANCE CRITERIA: {benchmark['acceptance_criteria']}")
        lines.append(f"RISK MITIGATION & CONTROLS (ISO 14971): {benchmark['risk_controls']}")
        lines.append(f"CONTROL OF RECORDS & RETENTION (ISO 13485 §4.2.5): {benchmark['records_retention']}")

        if web_snippets:
            lines.append("CURRENT INDUSTRY WEB ANALYSIS INSIGHTS:")
            for s in web_snippets[:2]:
                lines.append(f"  • {s}")

        return "\n".join(lines)


# Singleton instance
web_analysis_service = WebAnalysisService()
