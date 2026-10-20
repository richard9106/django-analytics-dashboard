# NuviaMy Clinical Processing Schedule

Version NUVIA SCHEDULE 2026 10 15 v1

This Schedule identifies the particular processing agreed by the Customer and NuviaMy. Attach the completed, signed version to the Data Processing Agreement and, where applicable, the HIPAA Business Associate Agreement. Uncompleted fields and unverified providers must be resolved before clinical approval; silence does not authorize a provider, transfer or clinical-data category.

## 1 Customer and contract references

Customer legal name: [CUSTOMER LEGAL NAME]. Workspace identifier: [WORKSPACE ID]. Customer representative and title: [NAME AND TITLE]. Customer privacy and incident contact, monitored email and alternate contact: [CONTACTS].

NuviaMy representative: Richard Andres Marles Bonilla, Calle Paciente Inglés 22, 50019 Zaragoza, Spain. Contract contact: marleswebinfo@gmail.com. Operational contact: support@nuviamy.com. Security follow-up shall move to an agreed secure channel; general support mail must not carry PHI.

DPA version: [EXECUTED DPA VERSION]. BAA version or reason not applicable: [REFERENCE AND ROLE ASSESSMENT]. Service agreement version and date: [REFERENCE]. Record-retention instruction reference: [REFERENCE]. Scope jurisdictions and professional discipline: [COUNTRIES STATES AND DISCIPLINE]. Approved processing start date: [DATE].

## 2 Processing description

Subject matter and purpose: hosting the Customer’s authorized professional workspace to organize its practice and make records available to authorized personnel and patients according to the Customer’s instructions. NuviaMy does not decide diagnoses, treatment or patient eligibility.

Operations: collection through authorized forms; storage; organization; retrieval; permission-controlled access; note creation and signature; linked correction where supported; authorized disclosure; export; approved backup and recovery; and instructed return or deletion. Select the actual enabled operations and integrations: [ENABLED SCOPE].

Data subjects: [PATIENTS ADULTS OR MINORS AS APPLICABLE], their authorized representatives, emergency contacts and the Customer’s personnel whose data is contained in the practice records. Confirm whether minors are included and any additional authorization controls: [SCOPE].

Data categories: identification and contact details; appointment details; relevant history, diagnoses, treatment plans, ordinary progress notes and signatures; approved documents; relevant billing records; and access/audit metadata. Select only necessary categories: [APPROVED CATEGORIES]. Clinical data may include health and other sensitive information under applicable law.

Excluded unless separately approved: separately maintained HIPAA psychotherapy notes; records regulated by 42 CFR Part 2; any category or integration outside the selected scope. Subscription payment card information is entered on Stripe’s hosted payment page and shall not be stored in clinical notes or sent to general support.

Frequency and duration: ongoing during the approved service, followed only by the agreed exit and lawful restricted-retention periods below. The scope excludes sale, advertising, independent AI training and independent research use.

## 3 Locations and provider authorizations

NuviaMy administers the service from Spain. The operator has reported the current VPS is in Europe; its precise contracted location remains to be recorded. A possible future New York move requires a new review before it happens. No promise that all data stays in the United States is made.

For each proposed service below, complete the legal entity, contract and location evidence. A provider is authorized for clinical data only when both parties record approval and all applicable agreements cover the exact service, plan, locations, support access and downstream processing. Provider-issued agreements may be used if reviewed and adequate; a provider is not bound by this Schedule alone.

Contabo VPS. Function: application hosting, database, local files and operational logs. Contracting legal entity: [VERIFY]. Service and plan: [VERIFY]. Storage, backup and support locations: [VERIFY]. Executed DPA reference: [VERIFY]. Applicable BAA coverage: [VERIFY OR REMOVE PHI PROCESSING]. Customer authorization: [APPROVED WITH DATE OR NOT AUTHORIZED].

Cloudflare R2. Function: uploaded documents and encrypted database backups. Contracting legal entity and account: [VERIFY]. Exact R2 product coverage, bucket jurisdiction and access locations: [VERIFY]. DPA, transfer basis and applicable BAA: [VERIFY]. Customer authorization: [APPROVED WITH DATE OR NOT AUTHORIZED]. Encryption alone does not resolve HIPAA subcontractor status.

Cloudflare network and Email Routing. Functions: [VERIFY ACTUAL NETWORK SERVICES]; support forwarding where enabled. Contracting entity, locations, contracts and actual data flow: [VERIFY]. General support routing is limited to nonclinical communications. Clinical traffic or PHI handling requires a separately verified role and applicable contractual coverage: [APPROVAL OR RESTRICTION].

Brevo SMTP and the operator’s Gmail support inbox. Function: account and nonclinical service notifications. Contracting entities, retention and DPA references: [VERIFY]. Clinical-data transmission is not authorized in this Schedule. Recovery links and account identifiers still require appropriate safeguards; no patient content shall be placed in message bodies, subjects or attachments.

Optional Google Calendar Gmail and Drive. Function and specific account/plan: [VERIFY IF REQUESTED]. Services, data fields, permissions, sharing settings, locations, agreements and applicable BAA: [VERIFY]. Clinical use remains unapproved until that integration is expressly authorized; enabling OAuth alone is not approval.

Optional Sentry monitoring. Function: technical diagnostics. Contracting entity, plan, retention, locations, filtering evidence and DPA: [VERIFY]. PHI is not authorized in diagnostics under this Schedule. If PHI cannot reliably be excluded, disable the flow or obtain and verify the required clinical scope and agreements before use.

Stripe. Function: NuviaMy SaaS subscription payments and, separately, any future approved patient-billing flow. Record the actual controller/processor role and terms for each function: [VERIFY]. Do not transmit clinical notes, diagnosis or treatment detail. Ordinary payment processing does not automatically determine BAA obligations for every additional Stripe use. Patient-billing PHI flows require separate assessment before approval.

## 4 Security responsibilities and evidence

For every measure record its implemented scope, responsible party, evidence date and unresolved limitation. Repository code or this list alone does not establish operating effectiveness.

Authentication and access: [EVIDENCE AND CUSTOMER RESPONSIBILITIES]. Current operational baseline includes credentials and session controls; mandatory MFA is not currently enabled. Do not represent MFA as implemented. Record the risk assessment and required authentication changes before clinical approval.

Transport, storage and keys: [TLS EVIDENCE, DATABASE AND VOLUME ENCRYPTION, DOCUMENT ENCRYPTION, BACKUP ENCRYPTION, KEY CUSTODY AND RECOVERY]. Application encryption of selected fields or OAuth tokens does not prove full database, disk or document encryption.

Audit and signed records: [ACCESS AND CHANGE COVERAGE, PROTECTION, REVIEW AND RETENTION]. Record how authorized corrections preserve the original and how any missing amendment workflow is handled before approving that use.

Backups and recovery: [SCOPE, INDEPENDENT COPY, RESTORE EVIDENCE, MONITORING AND RESPONSIBLE PERSON]. Agreed recovery point objective: [VALUE OR NO GUARANTEE]. Agreed recovery time objective: [VALUE OR NO GUARANTEE]. Do not infer guaranteed recovery from a single successful restore exercise.

Uploads, support and external services: [CONTENT VALIDATION, ACCESS CONTROLS, MALWARE RISK DECISION, SECURE SUPPORT CHANNEL AND INTEGRATION FILTERING]. Record the clinical validation and security review references: [REFERENCES].

## 5 Incidents and rights requests

Customer monitored contact and alternate: [CONTACTS]. NuviaMy monitored incident contact and alternate: [CONFIRMED CONTACTS]. Secure incident-detail channel: [CHANNEL]. DPA notice is without undue delay; BAA notice is without unreasonable delay and subject to its legal ceiling. Any additional contractual deadline: [AGREED DEADLINE OR NONE]. Do not describe an unapproved 24-hour or 72-hour service promise as implemented.

Individual request routing and responsible person: [PROCESS]. Information/export formats and response process: [FORMATS AND PROCESS]. Any applicable shorter legal deadline or delegated notice role: [DETAILS]. Routine unsuccessful security-incident summary reporting, if agreed: [FREQUENCY AND SCOPE OR NO EXCEPTION].

## 6 Retention exit and transfers

Clinical retention instruction, applicable jurisdiction/profession/age categories and legal-hold process: [APPROVED REFERENCE]. A single universal medical-record retention period is not selected by this template.

Export window after the processing service ends: [AGREED PERIOD]. Export format, covered records, attachments and audit/signature evidence: [DETAILS]. Customer return or deletion election and authorized contact: [ELECTION]. Active-data deletion timetable: [AGREED PROCESS AND DEADLINE]. Backup expiry and deletion propagation on restore: [VERIFIED MAXIMUM PERIOD AND PROCESS]. Required legal retention, reason and restricted-access safeguards: [DETAILS OR NONE]. Confirmation of completed return/destruction: [METHOD AND CONTACT]. These fields must be agreed before clinical approval; cancellation alone is not a destruction order.

Restricted transfers, if any: [ACTUAL EXPORTER IMPORTER AND ROLES]. Applicable legal mechanism and evidence, including an adequacy decision or executed standard contractual clauses with the correct module where required: [REFERENCE]. Transfer assessment and supplementary measures: [REFERENCE]. No SCC is executed or incorporated merely by naming it in this Schedule.

## 7 Approval and signatures

The parties confirm that the completed Schedule accurately reflects their agreed scope. Provider contracts and security evidence must support the approved entries before real clinical data is enabled. Any later material change to regions, services, data categories or subprocessors follows the governing agreements and required notice or authorization process.

For the Customer

Legal name and representative: [NAME AND TITLE]

Signature: ______________________________    Date: __________________

For NuviaMy

Richard Andres Marles Bonilla

Signature: ______________________________    Date: __________________

Workspace clinical approval reference and date, recorded only after the prerequisites are met: [APPROVAL REFERENCE OR NOT APPROVED]
