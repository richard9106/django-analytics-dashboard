# NuviaMy Clinical Processing Schedule

Version NUVIA SCHEDULE 2026 10 20 v3

One shared Schedule for the Data Processing Agreement and, where applicable, the HIPAA Business Associate Agreement. Complete the fields below before signing. Real clinical data remains unapproved until the provider agreements, safeguards and retention arrangements are verified and NuviaMy confirms approval in writing. Paying or signing alone does not provide that approval.

Customer legal name and workspace: [NAME AND ID]. Authorized representative: [NAME AND TITLE]. Privacy and incident contact: [MONITORED EMAIL AND ALTERNATE]. Countries, states, profession and adult/minor scope: [SCOPE]. Executed DPA, applicable BAA or reason it is not required, and service agreement versions: [REFERENCES].

Provider: Richard Andres Marles Bonilla, trading as NuviaMy, Calle Paciente Inglés 22, 50019 Zaragoza, Spain. Contract contact: marleswebinfo@gmail.com. Service contact: support@nuviamy.com.

## 1 What we store and why

NuviaMy handles practice records on the Customer’s instructions: collection, storage, authorized access, organization, signature, lawful correction, export, backup, recovery and agreed deletion. Processing is ongoing during the approved service and agreed exit period. The Customer makes clinical decisions and supplies lawful instructions.

People covered: the approved patients, their representatives and emergency contacts, and relevant practice personnel. Data may include contact information, appointments, health history, diagnoses, treatment plans, ordinary progress notes and signatures, documents, billing records and access logs. Selected data and enabled features: [APPROVED CATEGORIES AND FEATURES]. Minors require the agreed authorization controls: [CONTROLS OR EXCLUDED].

We do not use these clinical records for advertising, sale or independent AI training. Separately maintained HIPAA psychotherapy notes and records regulated by 42 CFR Part 2 are excluded unless separately agreed with suitable controls. Subscription card details are entered on Stripe’s hosted page.

## 2 Who handles the data and where

NuviaMy is administered from Spain. Since October 20, 2026, the production application, PostgreSQL database and server logs are hosted on Amazon EC2 in AWS US East (Northern Virginia), us-east-1. Private documents and scheduled encrypted database backups use separate Amazon S3 buckets in that region. Remote administration from Spain and provider support mean this is not a promise that all access or processing stays in the United States.

AWS provides the active hosting and storage infrastructure. The operator confirms acceptance of the AWS Business Associate Addendum for the production account; the contractual text has been reviewed. Before executing this Schedule, record the applicable AWS contracting entity, DPA and transfer terms, account-specific BAA acceptance reference and date, and support scope: [PRIVATE CONTRACT REFERENCES]. The BAA covers the qualifying account and eligible services subject to its conditions; it does not approve every NuviaMy feature or integration.

Cloudflare provides DNS; the production cutover records DNS-only routing to AWS. Any later proxy, caching or traffic inspection requires assessment before receiving affected data. Cloudflare Email Routing, Brevo SMTP and the operator’s Gmail inbox handle account/service communications, including authentication messages where configured. General email and support are not approved for clinical content. Record their exact legal entities, services, locations, retention and contracts before approving the relevant flows: [COMMUNICATIONS REFERENCES].

Google Calendar, Gmail and Drive are optional integrations. Google OAuth verification remains pending as of this version. Calendar exports use neutral reserved-time blocks without patient names, notes, meeting links or locations; even scheduling metadata requires assessment. Drive exports and Gmail flows require approval of the specific account, service, fields and agreements before clinical use. Sentry, where enabled, is restricted to minimized structural diagnostics; PHI is not authorized there. If a flow cannot exclude unapproved data, do not enable it for clinical use.

Stripe handles SaaS subscription billing. Do not send diagnoses or clinical notes to Stripe. Any patient-billing use requires its own assessment. The role and contract must match the actual service.

Authorized providers and integrations, recording for each its legal entity, exact service/plan, data, storage/support locations, executed contract references and approval date: [COMPLETE VERIFIED ENTRIES HERE]. Pending entries are not clinical-data authorizations. Any restricted transfer requires its actual legal basis and assessment: [REFERENCE OR NONE]. Naming an SCC does not execute one. Provider changes follow the DPA notice and objection process.

Historical recovery material may remain on the stopped Contabo origin, legacy R2 storage and encrypted operator recovery media. They are not active production destinations. Before clinical approval, identify the actual retained data and approved custodians, contractual coverage and retirement or restricted-retention plan: [LEGACY COPY DISPOSITION]. Do not reactivate an outdated origin or erase records without authorized reconciliation and retention instructions.

## 3 How we protect data and handle problems

Implemented safeguards include HTTPS, practice-scoped permissions, protected audit records, encrypted integration tokens, session expiry and revocation, and signed notes with immutable signed addenda. October 20 operational evidence records email two-step sign-in enabled; optional authenticator TOTP is separate and remains deferred in the documented baseline. Customer account recovery and privileged-access settings must be confirmed before approval.

AWS checks on October 20 confirmed an encrypted EC2 root volume and private S3 buckets with AES256 default encryption, versioning and public-access blocks. Database backups are additionally encrypted before upload to the separate backup bucket using the host role. The cutover evidence records an authenticated backup retrieval, restore into a disposable database and comparison of all 52 SQL table counts, plus document integrity checks. Daily encrypted instance snapshots retain seven recovery points. These controls do not establish WORM storage, independent key custody, tested alerting or a guaranteed recovery time.

The backup bucket currently expires current backups after 35 days and noncurrent versions 35 days after becoming noncurrent; this is not a strict total-age cap. Document versions have no automatic lifecycle deletion. These are operational settings, not an approved clinical retention policy. Complete the clinical/security review, logging and log-retention verification, key custody, monitoring and recovery objectives: [REVIEW REFERENCES AND RESPONSIBLE PERSON]. Any guaranteed recovery objective or extra incident deadline: [EXPRESSLY AGREED VALUE OR NONE]. Required unresolved safeguards prevent clinical approval.

The Customer manages its staff permissions and devices. NuviaMy remains responsible for its own safeguards. Incident notice follows the DPA and applicable BAA, without waiting for a complete investigation. Verified incident contacts and a secure channel for details: [CONTACTS AND CHANNEL]. Do not send patient details to general support email.

Individual rights requests go to the verified Customer contact. Assistance and response process: [PROCESS AND RESPONSIBLE PERSON]. Authorized practice exports include JSON records, available files and signature information; clinical exports include signed addenda. PDF summaries have disclosed content limits and are not the complete archive. Signed records retain their original, with lawful corrections linked rather than silently overwritten.

## 4 What happens when the service ends

Cancellation does not automatically delete records. The Customer identifies the retention rules for its profession, jurisdiction, patient ages and legal holds: [APPROVED INSTRUCTION]. We do not set a universal clinical retention period or promise indefinite storage.

Complete before clinical approval: export window and format, including documents and signature/audit evidence [DETAILS]; return or deletion choice [CHOICE]; active-data deletion deadline [PERIOD]; verified maximum backup expiry and deletion on restore [PERIOD AND PROCESS]; legally required retention and restricted access [DETAILS OR NONE]; completion confirmation [METHOD]. Any infeasible return/destruction remains protected and limited under the governing agreements.

Both parties approve only the completed scope. This Schedule does not replace the agreements with providers or amend prices and cancellation terms. Attach this exact version to the executed contracts.

Customer legal name and authorized representative: [NAME AND TITLE]. Signature: ____________________ Date: __________

For NuviaMy, Richard Andres Marles Bonilla. Signature: ____________________ Date: __________

Clinical approval reference and start date: [REFERENCE AND DATE OR NOT APPROVED].
