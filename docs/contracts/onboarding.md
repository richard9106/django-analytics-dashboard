# Clinical contract onboarding

Implementation prepared October 20, 2026. Deployment and clinical approval are separate actions; this document does not record a production rollout.

## Customer flow

The free signup and cardless trial retain their existing behavior. Owners see a clinical onboarding prompt on Overview and a Contracts link under Settings and Profile settings. Other staff and portal users cannot read, download or sign the practice contracts.

1. The owner submits the practice legal identity, registered address, authorized representative and title, privacy/incident contacts, jurisdiction, patient-age scope and HIPAA role explanation. Authority is explicitly confirmed; patient information is not requested.
2. The request appears in the operator's Django admin queue. Submission is not acceptance of a BAA and creates no clinical permission.
3. An authorized NuviaMy operator prepares the complete customer-specific DPA, applicable BAA and shared schedule, replacing all placeholders and identifying the exact versions. The application does not automatically publish the unfinished templates from this directory.
4. The owner reviews the full texts in the app, downloads them, types the representative name and expressly signs with authority and intent. A recent authenticated session is required even when optional TOTP is disabled. The reviewed packet must be the latest one, and the review expires after 30 minutes.
5. The owner can download a ZIP containing the exact document texts, the complete canonical packet and a signature receipt for both parties. The receipt records identities, signing times, consent and the SHA256 packet digest. This is an application signature record, not a certificate-based PDF signature or an external identity-verification service.

Owners can submit corrected legal details as a new request. Previous requests and packets remain intact; superseded unsigned packets cannot be signed. A new request does not cancel an already executed agreement. Contract access remains available after the commercial trial expires.

## Operator preparation and execution

Use Django admin with an active superuser authorized to bind NuviaMy. Contract records are not exposed to ordinary practice administrators, even if they otherwise manage staff or billing.

- Review **Clinical contract requests** and use the latest request for the practice. This initial implementation uses the admin queue; it does not send new contract notifications automatically.
- Complete the customer-specific texts using the DPA, BAA where applicable and schedule v3 in this directory. Resolve the remaining infrastructure/legal references, transfer terms, retention, exit instructions, scope and relevant review requirements before execution. Review a claimed HIPAA exemption rather than treating the selection as proof.
- Under **Clinical contract bundles**, add the request, unique packet/version reference, complete texts and the actual provider signer's name and title. Remove template brackets and blank signature lines, replacing the latter with the applicable electronic-execution wording. The operator is responsible for substantive completeness; placeholder detection is not legal review.
- Explicitly check the provider execution declaration before saving. Saving publishes an immutable packet and records the authenticated operator as the NuviaMy signatory. No signature is fabricated from registration, Stripe payment or merely viewing a page. Use a new packet/version to replace an unsigned offer; editing/deleting existing evidence is disabled.
- After customer signature, inspect **Clinical contract signatures** and retain/download the exact executed packet. Assess amendments and any previously signed versions under their actual terms.

## Evidence and security

Requests, provider-executed packets and customer signatures are append-only in the application and protected by PostgreSQL UPDATE, DELETE and TRUNCATE triggers. Practice/user references are protected from cascading deletion. Request/publication/signature operations serialize on the practice row; uniqueness and transaction boundaries prevent duplicate signature evidence. Document text is rendered as escaped text. State-changing requests require CSRF tokens, and owner POST endpoints are rate limited. Contract read, denial, download and signing events are audited without document bodies in audit metadata. Responses are private and not cacheable.

Database administrators and migration-role operators remain privileged. SHA256 integrity evidence does not remove the need for backups, access review or operational custody. SQLite does not provide the PostgreSQL trigger protections.

## Release and scope

Apply migrations 0007 through 0009 using the established migration role, then refresh runtime grants through the existing deployment process. Build static assets so `contracts.css` is included in the production manifest. No credentials, customer agreements or private AWS contracts are embedded in static assets or committed templates.

Contract completion does not change subscription status or unlock clinical functionality. The preview restriction remains in force until a separately authorized clinical release. This implementation does not add a clinical approval engine or determine from entered record text whether data is fictional. It also does not assert that the contract templates have received independent legal approval. Resolve the remaining clinical gates before allowing real patient data.
