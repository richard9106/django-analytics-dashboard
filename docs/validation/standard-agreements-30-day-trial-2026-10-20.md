# Standard agreements and 30-day trial — October 20, 2026

## Result

New owners accept a published standard offer during signup: Terms of Use, DPA, applicable BAA and Standard Processing Schedule, with acknowledgement of the Privacy Notice. Signup identifies the practice legal name/address and the authorized owner and title. Acceptance is required and unchecked. Full documents are available before submission at `/accounts/agreements/`.

The agreement covers the cardless trial and subsequent subscription. Ordinary accounts no longer wait for manual customer-specific document preparation or countersignature. The provider’s published offer expressly identifies Richard Andres Marles Bonilla, trading as NuviaMy. The retained consent is the exact text shown by the checkbox. It does not imply a government certification or remove security/subprocessor duties.

The standard schedule covers real ordinary client records during the trial. Separately maintained HIPAA psychotherapy notes and Part 2 records remain excluded without a separate arrangement. Optional external clinical integrations require assessment and appropriate contracts. The scope excludes clinical content in account/service email, general support, Sentry diagnostics and Stripe metadata. AWS infrastructure and Spanish administration are disclosed; no US-only-access or universal HIPAA-certification claim is made.

## Existing accounts and evidence

Existing owners see an Overview prompt and accept from Settings → Contracts with recent authentication. No previous account is marked as having accepted through a data migration. The dashboard prompt disappears after acceptance. This release does not add a global write block to legacy accounts; the agreement requirement is explicitly presented to their owner. Historical custom requests, signed packets and signatures remain preserved under their own terms. The old custom request UI is secondary at `/accounts/contracts/?custom=1`.

`StandardAgreementAcceptance` stores the exact document texts, versions, customer identity, provider offer, consent and acceptance timestamp. SHA-256 covers the complete snapshot, including its timestamp. Django and PostgreSQL prevent updates, deletion and truncation. One practice/version can produce only one receipt; the practice row lock handles concurrent acceptance. A stale form digest is rejected rather than silently accepting revised text. Downloads use the retained snapshot, not the current public offer, and are owner-only and tenant-scoped. Download ZIP contains the receipt, DPA/BAA/schedule TXT and Terms/Privacy HTML. Evidence can be inspected by authorized superusers without edit/add/delete controls.

## Trial and billing

New ordinary trials last exactly 30 days from signup without card/customer/subscription creation. `practices.0011` extends existing ordinary periods only when they are exactly 15 days, measured from the original start. This includes expired trials if their recalculated deadline is still in the future; it does not restart old trials. Custom lengths, annual invitations and active/trialing/past-due/unpaid subscription practices are unchanged. Re-running does not add another extension. Reversing the migration deliberately does not shorten a granted trial.

Checkout remains a voluntary action that starts paid billing immediately, without an additional Stripe trial. There is no automatic conversion, charge or deletion at trial expiry. Authorized reading, export and contract access remain available while subscription-controlled writes are restricted. This deliberately retains NuviaMy’s established exit behavior rather than copying SimplePractice’s trial-account deletion policy.

## Checks

Targeted tests cover signup rollback for stale/missing acceptance, 30-day expiry, legal versions, existing owner acceptance, exact retained downloads, cross-tenant/role denial, recent authentication, repeat/concurrent submissions, immutable evidence, dashboard prompt and idempotent migration exclusions. PostgreSQL checks exercise direct SQL update/delete/truncate rejection and concurrent acceptance. Historical custom-contract tests remain in place.

See the commit/PR checks for the final full-suite result and rollout status. This document does not itself claim a production deployment or completion of outstanding security/compliance review.

## Sources used for the design

- [SimplePractice BAA acceptance during trial signup](https://support.simplepractice.com/hc/en-us/articles/360018696052-SimplePractice-BAA-Terms-of-Service-and-Trust-Security-information)
- [SimplePractice trial FAQ](https://www.simplepractice.com/features/faqs/)
- [HHS: electronic business associate contracts](https://www.hhs.gov/hipaa/for-professionals/faq/are-business-associate-contracts-in-electronic-form-acceptable/index.html)
- [HHS: business associate contract provisions](https://www.hhs.gov/hipaa/for-professionals/covered-entities/sample-business-associate-agreement-provisions/index.html)

HHS accepts electronic written BA contracts subject to applicable contract law; a competitor’s workflow or the sample clauses alone are not a legal-validity or compliance determination for NuviaMy.
