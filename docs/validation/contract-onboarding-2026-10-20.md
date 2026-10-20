# Clinical contract onboarding validation

Prepared October 20, 2026. Local implementation and synthetic-data verification only; no production deployment, customer signature or clinical approval was performed.

## Verified

- Nineteen contract-flow tests pass on an isolated PostgreSQL 16 cluster, including owner-only access, cross-practice denial, required authority/consent, document escaping, stale review/version rejection, corrected requests, idempotency, download contents and immutable evidence.
- A separate run passed twenty tests: the contract tests plus the existing concurrent authentication-factor test. Concurrent signature attempts from two workers produce one signature and one signing event. The disposable-test teardown explicitly handles the new protected tables; production trigger protections remain enabled.
- Direct PostgreSQL UPDATE, DELETE and TRUNCATE attempts are rejected for contract requests, bundles and signatures.
- Django system checks and migration consistency checks pass. The existing cookie, diagnosis picker, appointment calendar, client-session picker and session-duration JavaScript checks pass. Whitespace checks pass.
- Browser verification with synthetic accounts on desktop and a 390px mobile viewport: request submission, full document review, recent credential verification, electronic signature, copy download and corrected-request submission. No horizontal overflow was observed. Settings navigation and retained signed history were checked.

## Limits and release

A supplemental full-suite run was stopped after 247 passing tests out of 626 discovered; it did not complete, so full CI remains a release check. The broad supplemental run used a fast password hasher only for synthetic tests; production password settings were not changed. The final focused contract runs used the project's ordinary test settings.

Publishing requires a real authorized NuviaMy operator to complete and expressly execute the customer-specific packet. No unfinished template is auto-published. Copies are downloadable ZIP packets with plain-text agreements, a canonical JSON snapshot and a signature receipt; this does not create a cryptographically certified PDF or independently verify a signer's identity.

The code does not approve clinical use or change the trial/payment lifecycle. It preserves the existing fictional-data preview restriction; it does not add a separate clinical approval engine or infer whether entered records are real. See docs/contracts/onboarding.md for operator and deployment instructions.
