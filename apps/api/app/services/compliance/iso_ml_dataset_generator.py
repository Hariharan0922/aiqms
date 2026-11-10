"""ISO 13485:2016 Machine Learning Training Dataset Generator.

Extracts authoritative clause text from the ISO 13485:2016 PDF / database,
synthesizes realistic QMS operational variations, audit scenarios, and
produces labeled datasets for:
1. Multi-task ML classification (Clause, Category, Procedure & Record flags)
2. Semantic similarity and gap detection
3. Instruction fine-tuning (SFT) for LLMs (Alpaca / OpenAI format)
"""

from dataclasses import dataclass, asdict
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.compliance import ISOClause

logger = logging.getLogger(__name__)


# Domain knowledge dictionary providing realistic QMS operational scenarios
# for each major ISO 13485 clause to augment ML model generalizability.
DOMAIN_QMS_SCENARIOS: Dict[str, List[str]] = {
    "4.1.2": [
        "The manufacturer shall determine the sequence and interaction of quality processes across design, manufacturing, and distribution.",
        "Application of risk-based approach to the control of quality management system processes per ISO 13485.",
        "Quality process mapping identifying inputs, outputs, controls, and process owners.",
    ],
    "4.1.5": [
        "Control of outsourced sterilization services through signed quality agreements and supplier audits.",
        "The organization retains full regulatory responsibility for contract manufacturing of catheter subassemblies.",
        "Outsourced process controls must be documented in a written quality agreement with supplier KPIs.",
    ],
    "4.1.6": [
        "Validation of enterprise ERP software and cloud eQMS prior to deployment in commercial release.",
        "Computer system validation (CSV) protocol for automated inspection camera software per GAMP 5.",
        "Software validation procedure proportionate to the risk of medical device nonconformance.",
        "Revalidation protocol for software updates to electronic batch record system.",
    ],
    "4.2.2": [
        "Quality manual defining the scope of the ISO 13485 quality management system and documented exclusions.",
        "Justification for exclusion of design and development clause 7.3 for contract manufacturer of sterile drapes.",
        "QMS manual outlining corporate quality policy, process interactions, and governance structure.",
    ],
    "4.2.3": [
        "Medical Device File (MDF) for coronary balloon catheter containing device specifications, intended use, and drawings.",
        "Device Master Record (DMR) detailing bill of materials, manufacturing routing, assembly procedures, and QC test specifications.",
        "The manufacturer shall establish and maintain a medical device file for each family of orthopaedic implants.",
        "DMR procedures for packaging, sterilization parameters, measuring, monitoring, and labeling.",
    ],
    "4.2.4": [
        "Standard operating procedure for document control, document approval matrix, and version numbering.",
        "Engineering Change Order (ECO) workflow for updating assembly drawings and work instructions.",
        "Obsolete document retention procedure ensuring archived specs remain available for device lifetime plus 2 years.",
        "Distribution control ensuring only active revision C work instructions are accessible at cleanroom workstations.",
    ],
    "4.2.5": [
        "SOP for control of quality records, electronic signature compliance, and record retention periods.",
        "Batch production records and sterilization certificates shall be archived for at least 5 years from device distribution.",
        "Confidential health data protection in clinical evaluation files and device complaints per HIPAA and GDPR.",
        "Records shall remain legible, readily identifiable, and retrievable in cloud storage.",
    ],
    "5.1": [
        "Top management commitment declaration establishing quality objectives and resource allocation for medical device safety.",
        "Executive leadership communication of customer regulatory requirements and quality policy across all facilities.",
    ],
    "5.2": [
        "Customer focus procedure ensuring patient safety and regulatory requirements are defined, met, and periodically reviewed.",
        "Customer requirements gathering for specialized pediatric cardiac catheters.",
    ],
    "5.3": [
        "Corporate Quality Policy signed by the Chief Executive Officer committing to ISO 13485 compliance and device effectiveness.",
        "Quality policy displayed in manufacturing areas and communicated during new employee onboarding.",
    ],
    "5.4.1": [
        "Annual quality objectives dashboard tracking first-pass yield, customer complaint rate, and supplier on-time delivery.",
        "Measurable quality targets established for sterile packaging defect reduction below 0.05%.",
    ],
    "5.4.2": [
        "Quality management system planning procedure ensuring QMS integrity is maintained during facility relocation.",
        "Change plan for migrating to automated optical inspection while maintaining ISO 13485 certification.",
    ],
    "5.5.1": [
        "Organizational chart and job descriptions defining authority and independence of Quality Assurance personnel from production.",
        "Responsibility and authority matrix granting Quality Control inspectors the authority to halt nonconforming production lines.",
    ],
    "5.5.2": [
        "Management Representative appointment letter assigning responsibility for QMS performance reporting and ISO 13485 compliance.",
        "Management representative role description overseeing regulatory compliance and external notified body audits.",
    ],
    "5.5.3": [
        "Internal communication procedure defining monthly town halls and quality alert bulletins on customer feedback.",
    ],
    "5.6.1": [
        "Management review procedure requiring executive review meetings at planned semi-annual intervals.",
        "Management review agenda evaluating QMS suitability, effectiveness, audit findings, and resource needs.",
    ],
    "5.6.2": [
        "Management review inputs package including internal audit results, CAPA status, customer feedback, and post-market surveillance data.",
        "Executive review input data summarizing supplier quality scorecards and regulatory reporting metrics.",
    ],
    "5.6.3": [
        "Management review meeting minutes documenting executive action items, budget approvals, and QMS improvements.",
        "Management review outputs detailing resource allocations for cleanroom HVAC upgrades and additional QA personnel.",
    ],
    "6.1": [
        "Resource allocation plan funding new validation equipment and hiring qualified regulatory affairs specialists.",
    ],
    "6.2": [
        "Training matrix and competence evaluation procedure for cleanroom assembly operators and QC technicians.",
        "Personnel training records, job descriptions, and qualification records for soldering high-reliability electronics.",
        "Effectiveness check protocol for cleanroom gowning and ESD awareness training courses.",
    ],
    "6.3": [
        "Preventive maintenance procedure and schedule for ultrasonic welders, injection molding machines, and air compressors.",
        "Infrastructure requirements ensuring orderly material flow and segregation to prevent product mix-up during assembly.",
    ],
    "6.4.1": [
        "ISO Class 7 cleanroom work environment monitoring SOP covering airborne particles, differential pressure, and temperature.",
        "Personnel cleanliness, gowning protocol, nitrile gloves, and hairnet requirements in sterile device packaging cells.",
        "Temporary contractor supervision procedure for technicians entering controlled environmental areas.",
    ],
    "6.4.2": [
        "Bioburden and particulate contamination control procedure for surgical tools prior to final packaging.",
        "Handling procedure for dropped or potentially contaminated components in cleanroom assembly bays.",
    ],
    "7.1": [
        "Product realization quality plan defining verification, validation, risk management, and acceptance criteria for Model X.",
        "Risk management plan integrated into product realization lifecycle in accordance with ISO 14971.",
    ],
    "7.2.1": [
        "Customer requirements capture for customized surgical drill bits, including sterilization compatibility and torque specs.",
        "Determination of regulatory requirements applicable to Class IIb medical devices across EU and US markets.",
    ],
    "7.2.2": [
        "Contract review procedure ensuring technical capabilities and regulatory approvals exist before accepting OEM purchase orders.",
        "Sales order review verifying that customer request does not exceed validated sterilization dose or shelf-life claims.",
    ],
    "7.2.3": [
        "Customer communication protocol for dispatching product advisories, field safety notices, and handling technical inquiries.",
    ],
    "7.3.2": [
        "Design and development plan (DDP) for endoscopic camera outlining project phases, design reviews, and gate milestones.",
        "Design plan defining team roles, design verification activities, validation methods, and design transfer timeline.",
    ],
    "7.3.3": [
        "Design input requirements document detailing functional specifications, electrical safety (IEC 60601), and ISO 14971 risk mitigations.",
        "User needs translation into engineering design inputs for handheld ultrasound probe.",
    ],
    "7.3.4": [
        "Design outputs including assembly CAD models, bill of materials, circuit schematics, and packaging specifications.",
        "Design output verification matrix proving that all design inputs have corresponding verified outputs.",
    ],
    "7.3.5": [
        "Formal design review meeting records for Phase 2 breadboard testing attended by R&D, Quality, and Manufacturing engineers.",
        "Design review minutes approving transition from prototype stage to design verification.",
    ],
    "7.3.6": [
        "Design verification protocol testing tensile strength of balloon catheter joints with sample size $n=30$ and statistical justification.",
        "Electrical safety and electromagnetic compatibility (EMC) test report verifying compliance with design specifications.",
    ],
    "7.3.7": [
        "Design validation protocol conducting clinical usability evaluations with surgeons in simulated operating environment.",
        "Validation report confirming diagnostic software achieves 99.2% sensitivity on representative clinical image datasets.",
    ],
    "7.3.8": [
        "Design transfer protocol ensuring manufacturing work instructions, tooling, and test fixtures are verified before full-rate production.",
        "Production capability study demonstrating Cpk > 1.33 for critical catheter extrusion dimensions prior to commercial release.",
    ],
    "7.3.9": [
        "Design change control procedure assessing the impact of resin material substitution on biocompatibility and mechanical strength.",
        "Engineering change request (ECR) for printed circuit board revision requiring re-verification of firmware compatibility.",
    ],
    "7.3.10": [
        "Design History File (DHF) index compiling all design plans, inputs, outputs, verification reports, and validation records.",
        "The organization maintains a complete design and development file for each orthopedic bone plate family.",
    ],
    "7.4.1": [
        "Supplier evaluation and qualification SOP based on ISO 13485 certification, quality audits, and incoming defect rates.",
        "Approved Supplier List (ASL) maintenance and periodic re-evaluation scorecard for contract sterilizer.",
    ],
    "7.4.2": [
        "Purchasing information procedure requiring formal quality agreements, certificate of analysis (CoA), and change notification clauses.",
        "Purchase order specification for medical grade silicone tubing requiring vendor notification before formulation changes.",
    ],
    "7.4.3": [
        "Incoming inspection procedure for titanium bars, checking dimensional tolerances and metallurgical chemical composition test reports.",
        "Verification of raw material batches against acceptance sampling plan ANSI/ASQ Z1.4.",
    ],
    "7.5.1": [
        "Production traveler and Device History Record (DHR) documenting batch quantity, serial numbers, operator signoffs, and test results.",
        "Standard operating procedure for ultrasonic welding of medical infusion pump casings.",
    ],
    "7.5.2": [
        "Cleanliness specification and ultrasonic cleaning procedure for titanium implant screws prior to cleanroom packaging.",
        "Removal of machining oils and particulate contaminants from vascular stent surfaces.",
    ],
    "7.5.3": [
        "Field installation procedure and acceptance checklist for magnetic resonance imaging (MRI) scanners at hospital radiology suites.",
        "Installation qualification checklist signed by certified biomedical field service engineer.",
    ],
    "7.5.4": [
        "Servicing SOP and maintenance protocol for commercial ventilator fleet, including calibration of oxygen sensor.",
        "Analysis of service call logs to identify potential product reliability trends and complaint triggers.",
    ],
    "7.5.5": [
        "Sterilization batch records documenting ethylene oxide exposure time, temperature, humidity, and biological indicator results.",
        "Traceability of sterilization lot parameters linked directly to finished catheter batch records.",
    ],
    "7.5.6": [
        "Process validation master plan (PVMP) outlining IQ, OQ, PQ requirements for automated laser cutting of vascular stents.",
        "Installation, Operational, and Performance Qualification (IQ/OQ/PQ) protocol for automated blister sealing machine.",
        "Validation of computer software used in automated optical inspection (AOI) on the SMT electronics line.",
    ],
    "7.5.7": [
        "Sterilization process validation protocol compliant with ISO 11135 (EtO) or ISO 11137 (Gamma radiation).",
        "Sterile barrier packaging validation per ISO 11607-1 and ISO 11607-2, including dye penetration and bubble emission testing.",
        "Accelerated aging and real-time shelf life packaging integrity test protocol for sterile barrier pouches.",
    ],
    "7.5.8": [
        "Product identification and labeling SOP, including Unique Device Identifier (UDI) barcoding and lot tracking.",
        "Segregation and physical labeling of in-process subassemblies using color-coded quarantine and release bins.",
    ],
    "7.5.9": [
        "Traceability SOP detailing bidirectional tracking of pacemaker serialized units from raw components to patient implant recipient.",
        "Shipping package consignee records maintained to enable prompt recall or field corrective action.",
    ],
    "7.5.10": [
        "Customer-supplied component handling procedure, verifying incoming donor tissues or customer hardware integrity.",
    ],
    "7.5.11": [
        "Product preservation procedure specifying temperature and humidity limits during storage and air freight transit.",
        "Electrostatic discharge (ESD) protective packaging for sensitive implantable defibrillator electronics.",
    ],
    "7.6": [
        "Calibration program SOP for digital calipers, pressure gauges, and analytical balances traceable to NIST standards.",
        "Out-of-calibration investigation SOP assessing impact on previously accepted medical device lots.",
        "Validation of automated calibration logging software.",
    ],
    "8.2.1": [
        "Customer feedback procedure gathering post-market satisfaction data, surgeon surveys, and clinical usability reports.",
        "Feedback analysis integrated into periodic risk management file updates.",
    ],
    "8.2.2": [
        "Complaint handling standard operating procedure defining intake, medical assessment, investigation, and root cause determination.",
        "Complaint investigation procedure for reported balloon catheter burst during percutaneous coronary intervention.",
        "Timely complaint logging, sample return analysis, and closure within 30 days.",
    ],
    "8.2.3": [
        "Vigilance and regulatory reporting SOP for medical device adverse events to FDA (MDR) and European Competent Authorities (MIR).",
        "Adverse event escalation criteria requiring 15-day or 5-day expedited reporting for serious injury or patient death.",
    ],
    "8.2.4": [
        "Internal quality audit procedure defining annual audit schedule, auditor independence, checklists, and reporting.",
        "Internal audit nonconformance report (NCR) issued for lack of calibration records in cleanroom maintenance.",
    ],
    "8.2.5": [
        "Monitoring and measurement of manufacturing processes using statistical process control (SPC) charts and capability indices.",
    ],
    "8.2.6": [
        "Finished device release SOP requiring verification of all DHR inspection signoffs, sterilization records, and test results.",
        "Authorized QA release signature required before shipping coronary stents to distribution warehouses.",
    ],
    "8.3.1": [
        "Control of nonconforming product SOP establishing red-tagging, physical quarantine cage, and Material Review Board (MRB).",
        "Segregation and disposition procedure for nonconforming raw materials detected at incoming inspection.",
    ],
    "8.3.2": [
        "Nonconformance disposition before delivery: scrap, return to vendor, or authorized concession with technical justification.",
    ],
    "8.3.3": [
        "Actions for nonconforming product detected after delivery: field safety corrective action (FSCA) and advisory notice issuance.",
        "Medical device recall procedure defining health hazard evaluation (HHE), customer quarantine notice, and regulatory notification.",
    ],
    "8.3.4": [
        "Rework procedure requiring formal engineering evaluation of adverse impact on biocompatibility and re-inspection testing.",
        "Reworked catheter shafts must undergo 100% re-inspection against tensile strength acceptance criteria.",
    ],
    "8.4": [
        "Data analysis SOP tracking quality trends across complaints, audit findings, nonconformities, and supplier metrics.",
        "Statistical trend analysis using Pareto charts to identify common failure modes in syringe pumps.",
    ],
    "8.5.1": [
        "Continual improvement protocol utilizing quality policy, audit findings, CAPA trends, and management review outputs.",
    ],
    "8.5.2": [
        "Corrective Action (CAPA) standard operating procedure: problem statement, containment, root cause analysis (5-Whys/Fishbone), action plan.",
        "CAPA effectiveness verification protocol evaluating 3 consecutive production batches after tool modification.",
        "Verification that corrective actions do not compromise regulatory compliance or medical device safety.",
    ],
    "8.5.3": [
        "Preventive Action procedure analyzing near-misses, process capability degradation, and tool wear to preclude defects.",
        "Preventive maintenance optimization to prevent motor overheating in surgical drills.",
    ],
}


@dataclass
class MLTrainingSample:
    text: str
    clause_number: str
    category: str
    requires_documented_procedure: bool
    requires_record: bool
    source_type: str  # "pdf_normative", "pdf_summary", "pdf_notes", "qms_domain_scenario"
    page_start: Optional[int] = None
    page_end: Optional[int] = None


class ISO13485DatasetGenerator:
    """Generates comprehensive training, evaluation, and SFT datasets from ISO 13485:2016."""

    def __init__(self, db: Session):
        self.db = db

    def generate_classification_dataset(self) -> List[MLTrainingSample]:
        """Builds a rich multi-class, multi-target dataset covering all ISO 13485 clauses."""
        clauses = self.db.query(ISOClause).order_by(ISOClause.clause_number).all()
        if not clauses:
            from app.services.compliance.iso_knowledge_service import ISOKnowledgeService
            svc = ISOKnowledgeService(db=self.db)
            svc.sync_iso_knowledge_base()
            clauses = self.db.query(ISOClause).order_by(ISOClause.clause_number).all()
        samples: List[MLTrainingSample] = []

        for c in clauses:
            clause_num = c.clause_number
            category = c.category or "General"
            proc_req = bool(c.requires_documented_procedure)
            rec_req = bool(c.requires_record)
            p_start = c.page_start
            p_end = c.page_end

            # 1. Title and Header Representation
            samples.append(
                MLTrainingSample(
                    text=f"Clause {clause_num} {c.title}. Requirements for {category}.",
                    clause_number=clause_num,
                    category=category,
                    requires_documented_procedure=proc_req,
                    requires_record=rec_req,
                    source_type="pdf_title",
                    page_start=p_start,
                    page_end=p_end,
                )
            )

            # 2. Summary Requirements
            if c.summary_requirements:
                samples.append(
                    MLTrainingSample(
                        text=f"{c.title}: {c.summary_requirements}",
                        clause_number=clause_num,
                        category=category,
                        requires_documented_procedure=proc_req,
                        requires_record=rec_req,
                        source_type="pdf_summary",
                        page_start=p_start,
                        page_end=p_end,
                    )
                )

            # 3. Normative Text & Sentence Decomposition
            full_text = c.normative_text or c.clause_text or ""
            if len(full_text.strip()) > 20:
                # Add full normative block
                samples.append(
                    MLTrainingSample(
                        text=full_text,
                        clause_number=clause_num,
                        category=category,
                        requires_documented_procedure=proc_req,
                        requires_record=rec_req,
                        source_type="pdf_normative",
                        page_start=p_start,
                        page_end=p_end,
                    )
                )

                # Split into sentence-level / paragraph-level chunks
                raw_sentences = re.split(r"(?<=[.!?])\s+", full_text)
                for sentence in raw_sentences:
                    clean = sentence.strip()
                    if len(clean) > 35:
                        samples.append(
                            MLTrainingSample(
                                text=clean,
                                clause_number=clause_num,
                                category=category,
                                requires_documented_procedure=proc_req,
                                requires_record=rec_req,
                                source_type="pdf_sentence",
                                page_start=p_start,
                                page_end=p_end,
                            )
                        )

            # 4. Explanatory Notes
            if c.explanatory_notes and len(c.explanatory_notes.strip()) > 15:
                samples.append(
                    MLTrainingSample(
                        text=f"Note on {c.title}: {c.explanatory_notes}",
                        clause_number=clause_num,
                        category=category,
                        requires_documented_procedure=proc_req,
                        requires_record=rec_req,
                        source_type="pdf_notes",
                        page_start=p_start,
                        page_end=p_end,
                    )
                )

            # 5. Domain QMS Operational Scenarios
            domain_scenarios = DOMAIN_QMS_SCENARIOS.get(clause_num, [])
            for scenario in domain_scenarios:
                samples.append(
                    MLTrainingSample(
                        text=scenario,
                        clause_number=clause_num,
                        category=category,
                        requires_documented_procedure=proc_req,
                        requires_record=rec_req,
                        source_type="qms_domain_scenario",
                        page_start=p_start,
                        page_end=p_end,
                    )
                )

        logger.info("Generated %d ML training samples from ISO 13485:2016", len(samples))
        return samples

    def generate_llm_sft_dataset(self) -> List[Dict[str, Any]]:
        """Generates instruction-tuning (SFT) dataset for training LLMs on ISO 13485:2016 compliance."""
        clauses = self.db.query(ISOClause).order_by(ISOClause.clause_number).all()
        if not clauses:
            from app.services.compliance.iso_knowledge_service import ISOKnowledgeService
            svc = ISOKnowledgeService(db=self.db)
            svc.sync_iso_knowledge_base()
            clauses = self.db.query(ISOClause).order_by(ISOClause.clause_number).all()
        sft_records: List[Dict[str, Any]] = []

        for c in clauses:
            clause_num = c.clause_number
            title = c.title
            text = c.normative_text or c.clause_text or ""
            summary = c.summary_requirements or ""
            proc = "Yes (Documented Procedure Required)" if c.requires_documented_procedure else "No"
            rec = "Yes (Quality Records Required)" if c.requires_record else "No"

            # Instruction 1: Regulatory Standard Clause Query
            sft_records.append({
                "instruction": f"What are the specific requirements of ISO 13485:2016 Clause {clause_num} ({title})?",
                "input": "",
                "output": (
                    f"### ISO 13485:2016 Clause {clause_num}: {title}\n"
                    f"**Category:** {c.category}\n"
                    f"**Documented Procedure Mandated:** {proc}\n"
                    f"**Records Retention Mandated:** {rec}\n\n"
                    f"#### Core Normative Requirements:\n{text}\n\n"
                    f"#### Key Compliance Summary:\n{summary}"
                ),
                "messages": [
                    {"role": "system", "content": "You are an expert ISO 13485:2016 regulatory compliance auditor."},
                    {"role": "user", "content": f"What are the specific requirements of ISO 13485:2016 Clause {clause_num} ({title})?"},
                    {"role": "assistant", "content": (
                        f"ISO 13485:2016 Clause {clause_num} ({title}) falls under '{c.category}'.\n\n"
                        f"**Requirements:**\n{text}\n\n"
                        f"- Documented procedure required: {proc}\n"
                        f"- Records required: {rec}"
                    )},
                ]
            })

            # Instruction 2: Compliance Audit Scenario
            scenarios = DOMAIN_QMS_SCENARIOS.get(clause_num, [])
            for sc in scenarios:
                sft_records.append({
                    "instruction": f"Evaluate whether the following procedure complies with ISO 13485:2016 Clause {clause_num} ({title}).",
                    "input": sc,
                    "output": (
                        f"**Audit Findings for Clause {clause_num} ({title}):**\n"
                        f"- Standard Reference: ISO 13485:2016 Clause {clause_num}\n"
                        f"- Documented Procedure Obligation: {proc}\n"
                        f"- Recordkeeping Obligation: {rec}\n"
                        f"- Compliance Verdict: Compliant. The procedure addresses core requirements.\n"
                        f"- Auditor Recommendation: Ensure records are retained in compliance with Clause 4.2.5."
                    ),
                    "messages": [
                        {"role": "system", "content": "You are an ISO 13485 lead auditor evaluating medical device quality records."},
                        {"role": "user", "content": f"Evaluate whether this procedure complies with ISO 13485:2016 Clause {clause_num}:\n\"{sc}\""},
                        {"role": "assistant", "content": f"Verdict: Compliant. The excerpt addresses the intent of Clause {clause_num} ({title})."},
                    ]
                })

        return sft_records
