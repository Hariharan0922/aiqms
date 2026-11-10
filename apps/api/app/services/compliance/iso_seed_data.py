"""Authoritative ISO 13485:2016 standard clause definitions for medical device QMS traceability."""

ISO_13485_CLAUSES = [
    {
        "id": "ISO-13485-4.2.3",
        "clause_number": "4.2.3",
        "parent_clause_number": "4.2",
        "title": "Medical device file",
        "category": "Documentation requirements",
        "requires_documented_procedure": False,
        "requires_record": True,
        "clause_text": (
            "For each medical device type or medical device family, the organization shall establish and maintain "
            "one or more files either containing or referencing documents generated to demonstrate conformity to "
            "the requirement of this International Standard and compliance with applicable regulatory requirements. "
            "The content of the file(s) shall include: general description, specifications, procedures for manufacturing, "
            "packaging, storage, handling and distribution, procedures for measuring and monitoring, and installation requirements."
        ),
        "summary_requirements": (
            "- Establish Medical Device File (MDF) / Device Master File (DMF)\n"
            "- Include device specifications and intended use\n"
            "- Include manufacturing, packaging, and storage procedures\n"
            "- Include measuring, monitoring, and servicing procedures"
        ),
    },
    {
        "id": "ISO-13485-4.2.4",
        "clause_number": "4.2.4",
        "parent_clause_number": "4.2",
        "title": "Control of documents",
        "category": "Documentation requirements",
        "requires_documented_procedure": True,
        "requires_record": True,
        "clause_text": (
            "Documents required by the quality management system shall be controlled. The organization shall establish "
            "a documented procedure to define the controls needed to: review and approve documents for adequacy prior to issue; "
            "review, update as necessary and re-approve documents; ensure changes and current revision status are identified; "
            "ensure relevant versions of applicable documents are available at points of use; ensure documents remain legible and readily identifiable; "
            "prevent deterioration or loss of documents; prevent unintended use of obsolete documents."
        ),
        "summary_requirements": (
            "- Documented procedure for document control\n"
            "- Review and approval prior to issue\n"
            "- Revision status identification and change tracking\n"
            "- Availability of current versions at points of use\n"
            "- Retention of at least one obsolete document copy"
        ),
    },
    {
        "id": "ISO-13485-4.2.5",
        "clause_number": "4.2.5",
        "parent_clause_number": "4.2",
        "title": "Control of records",
        "category": "Documentation requirements",
        "requires_documented_procedure": True,
        "requires_record": True,
        "clause_text": (
            "Records shall be maintained to provide evidence of conformity to requirements and of the effective operation "
            "of the quality management system. The organization shall establish a documented procedure to define the controls needed "
            "for the identification, storage, security and integrity, retrieval, retention time and disposition of records. "
            "The organization shall define and implement methods for protecting confidential health information."
        ),
        "summary_requirements": (
            "- Documented procedure for record control\n"
            "- Controls for storage, protection, retrieval, and retention time\n"
            "- Records must remain legible, readily identifiable, and retrievable\n"
            "- Retention period defined (lifetime of device or regulatory minimum)"
        ),
    },
    {
        "id": "ISO-13485-6.4.1",
        "clause_number": "6.4.1",
        "parent_clause_number": "6.4",
        "title": "Work environment",
        "category": "Resource management",
        "requires_documented_procedure": True,
        "requires_record": True,
        "clause_text": (
            "The organization shall document the requirements for the work environment needed to achieve conformity "
            "to product requirements. If the conditions for the work environment can have an adverse effect on product quality, "
            "the organization shall document the requirements for the work environment and the procedures to monitor and control the work environment."
        ),
        "summary_requirements": (
            "- Document work environment requirements (temperature, humidity, cleanliness)\n"
            "- Establish monitoring and control procedures where environment affects product quality\n"
            "- Maintain environmental monitoring records"
        ),
    },
    {
        "id": "ISO-13485-6.4.2",
        "clause_number": "6.4.2",
        "parent_clause_number": "6.4",
        "title": "Contamination control",
        "category": "Resource management",
        "requires_documented_procedure": True,
        "requires_record": False,
        "clause_text": (
            "As appropriate, the organization shall plan and document arrangements for the control of contaminated "
            "or potentially contaminated product in order to prevent contamination of the work environment, personnel, or product. "
            "For sterile medical devices, the organization shall document requirements for control of contamination with microorganisms or particulate matter."
        ),
        "summary_requirements": (
            "- Document contamination control procedures\n"
            "- Airborne particle and bioburden control for cleanrooms\n"
            "- Gowning, cleaning, and sanitization protocols"
        ),
    },
    {
        "id": "ISO-13485-7.1",
        "clause_number": "7.1",
        "parent_clause_number": "7",
        "title": "Planning of product realization",
        "category": "Product realization",
        "requires_documented_procedure": False,
        "requires_record": True,
        "clause_text": (
            "The organization shall plan and develop the processes needed for product realization. "
            "The organization shall document one or more processes for risk management in product realization. "
            "Records of risk management activities shall be maintained. In planning product realization, "
            "the organization shall determine quality objectives, requirements for product, processes, documents, resources, "
            "and required verification, validation, monitoring, measurement, inspection and test activities."
        ),
        "summary_requirements": (
            "- Product realization planning\n"
            "- Documented risk management process (ISO 14971)\n"
            "- Determination of verification, validation, and acceptance criteria\n"
            "- Maintenance of risk management records"
        ),
    },
    {
        "id": "ISO-13485-7.3.5",
        "clause_number": "7.3.5",
        "parent_clause_number": "7.3",
        "title": "Design and development verification",
        "category": "Design and development",
        "requires_documented_procedure": True,
        "requires_record": True,
        "clause_text": (
            "Design and development verification shall be performed in accordance with planned and documented arrangements "
            "to ensure that the design and development outputs have met the design and development input requirements. "
            "The organization shall document verification plans that include methods, acceptance criteria and, as appropriate, "
            "statistical techniques with rationale for sample size. Records of the results and conclusions of the verification and necessary actions shall be maintained."
        ),
        "summary_requirements": (
            "- Documented verification plans with acceptance criteria\n"
            "- Sample size rationale and statistical techniques\n"
            "- Traceability from design outputs to design inputs\n"
            "- Verification test reports and records"
        ),
    },
    {
        "id": "ISO-13485-7.3.6",
        "clause_number": "7.3.6",
        "parent_clause_number": "7.3",
        "title": "Design and development validation",
        "category": "Design and development",
        "requires_documented_procedure": True,
        "requires_record": True,
        "clause_text": (
            "Design and development validation shall be performed in accordance with planned and documented arrangements "
            "to ensure that the resulting product is capable of meeting the requirements for the specified application or intended use. "
            "Validation shall be conducted on representative product (e.g. initial production units). "
            "The organization shall document validation plans that include methods, acceptance criteria and statistical rationale. "
            "Records of the results and conclusions of validation and necessary actions shall be maintained."
        ),
        "summary_requirements": (
            "- Documented validation plans on representative production units\n"
            "- Verification that product meets intended use and user needs\n"
            "- Clinical evaluation or performance evaluation where applicable\n"
            "- Records of validation results"
        ),
    },
    {
        "id": "ISO-13485-7.5.1",
        "clause_number": "7.5.1",
        "parent_clause_number": "7.5",
        "title": "Control of production and service provision",
        "category": "Production and service provision",
        "requires_documented_procedure": True,
        "requires_record": True,
        "clause_text": (
            "Production and service provision shall be planned, carried out, monitored and controlled to ensure that product "
            "conforms to specification. Documented procedures and work instructions shall define production controls, "
            "including qualifications of infrastructure, monitoring parameters, product release criteria, and labelling controls. "
            "The organization shall establish and maintain a record for each batch of medical devices that provides traceability (Device History Record)."
        ),
        "summary_requirements": (
            "- Documented manufacturing SOPs and assembly work instructions\n"
            "- Device History Record (DHR) / Batch manufacturing record\n"
            "- Documented equipment qualification and process parameters\n"
            "- Product acceptance and release criteria"
        ),
    },
    {
        "id": "ISO-13485-7.5.6",
        "clause_number": "7.5.6",
        "parent_clause_number": "7.5",
        "title": "Validation of processes for production and service provision",
        "category": "Production and service provision",
        "requires_documented_procedure": True,
        "requires_record": True,
        "clause_text": (
            "The organization shall validate any processes for production and service provision where the resulting output "
            "cannot be or is not verified by subsequent monitoring or measurement. The organization shall document procedures "
            "for process validation including: defined criteria for review and approval; qualification of equipment and personnel; "
            "use of specific methods, procedures and acceptance criteria; statistical techniques with sample size rationale; "
            "revalidation requirements."
        ),
        "summary_requirements": (
            "- Documented process validation procedure (IQ, OQ, PQ)\n"
            "- Defined acceptance criteria and equipment qualification\n"
            "- Personnel qualification and training\n"
            "- Criteria for revalidation when process changes occur"
        ),
    },
    {
        "id": "ISO-13485-7.5.8",
        "clause_number": "7.5.8",
        "parent_clause_number": "7.5",
        "title": "Identification",
        "category": "Production and service provision",
        "requires_documented_procedure": True,
        "requires_record": False,
        "clause_text": (
            "The organization shall document procedures for product identification through suitable means throughout product realization. "
            "The organization shall identify product status with respect to monitoring and measurement requirements throughout product realization. "
            "Identification of product status shall be maintained throughout production, storage, installation and servicing."
        ),
        "summary_requirements": (
            "- Documented procedure for product identification\n"
            "- Status identification (e.g. accepted, on hold, rejected)\n"
            "- Physical or electronic labeling throughout realization"
        ),
    },
    {
        "id": "ISO-13485-7.5.9",
        "clause_number": "7.5.9",
        "parent_clause_number": "7.5",
        "title": "Traceability",
        "category": "Production and service provision",
        "requires_documented_procedure": True,
        "requires_record": True,
        "clause_text": (
            "The organization shall document procedures for traceability. These procedures shall define the extent of traceability "
            "in accordance with applicable regulatory requirements and the records to be maintained. "
            "The organization shall maintain a record of the name and address of the shipping package consignee for each medical device."
        ),
        "summary_requirements": (
            "- Documented procedure for device and component traceability\n"
            "- Lot/batch number assignment and tracking\n"
            "- Traceability of raw materials, components, and personnel\n"
            "- Distribution records maintained"
        ),
    },
    {
        "id": "ISO-13485-8.2.4",
        "clause_number": "8.2.4",
        "parent_clause_number": "8.2",
        "title": "Internal audit",
        "category": "Measurement and improvement",
        "requires_documented_procedure": True,
        "requires_record": True,
        "clause_text": (
            "The organization shall conduct internal audits at planned intervals to determine whether the quality management system "
            "conforms to the planned arrangements, to ISO 13485, and to established requirements, and is effectively implemented and maintained. "
            "A documented procedure shall define responsibilities and requirements for planning and conducting audits, recording and reporting audit results."
        ),
        "summary_requirements": (
            "- Documented procedure for internal auditing\n"
            "- Audit schedule based on process importance and status\n"
            "- Auditor independence (auditors shall not audit their own work)\n"
            "- Documented audit reports and timely corrective actions"
        ),
    },
    {
        "id": "ISO-13485-8.3.1",
        "clause_number": "8.3.1",
        "parent_clause_number": "8.3",
        "title": "Control of nonconforming product",
        "category": "Measurement and improvement",
        "requires_documented_procedure": True,
        "requires_record": True,
        "clause_text": (
            "The organization shall ensure that product which does not conform to product requirements is identified and controlled "
            "to prevent its unintended use or delivery. A documented procedure shall define the controls and related responsibilities "
            "and authorities for the identification, documentation, segregation, evaluation and disposition of nonconforming product."
        ),
        "summary_requirements": (
            "- Documented procedure for nonconformance handling\n"
            "- Segregation and identification of nonconforming items\n"
            "- Disposition authority and evaluation (scrap, rework, concession)\n"
            "- Maintenance of nonconformance records (NCRs)"
        ),
    },
    {
        "id": "ISO-13485-8.5.2",
        "clause_number": "8.5.2",
        "parent_clause_number": "8.5",
        "title": "Corrective action",
        "category": "Measurement and improvement",
        "requires_documented_procedure": True,
        "requires_record": True,
        "clause_text": (
            "The organization shall take action to eliminate the cause of nonconformities in order to prevent recurrence. "
            "A documented procedure shall define requirements for: reviewing nonconformities (including complaints); "
            "determining the causes of nonconformities; evaluating the need for action; planning, documenting, and implementing corrective action; "
            "verifying that the corrective action does not adversely affect ability to meet requirements; reviewing the effectiveness of corrective action."
        ),
        "summary_requirements": (
            "- Documented CAPA procedure\n"
            "- Root cause investigation\n"
            "- Implementation and verification of corrective action\n"
            "- Verification of effectiveness\n"
            "- Maintenance of CAPA records"
        ),
    },
]
