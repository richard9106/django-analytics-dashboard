# AWS deployment and TLS preparation — 20 October 2026

Production remains on Contabo. AWS application activation marker is absent; no production DB or web service has been started there.

## TLS

- Installed Certbot on AWS and a dedicated HTTP ACME webroot.
- Existing Contabo NuviaMy virtual host forwards only ACME challenge paths to AWS. Added the named HTTP NuviaMy virtual host; all other NuviaMy traffic continues to the old app. Unrelated sites are unchanged.
- Issued an independent Let's Encrypt certificate for nuviamy.com and www.nuviamy.com on AWS, expiring 18 January 2027.
- Nginx now uses /etc/letsencrypt/live/nuviamy.com certificate paths. Keys remain root-only.
- certbot.timer active; deploy hook validates/reloads Nginx. certbot renew --dry-run --run-deploy-hooks succeeded.
- AWS preflight HTTPS remains maintenance-only (503) and validates the public certificate. Current origin health remains 200.

## Git deployment

PR: https://github.com/richard9106/django-analytics-dashboard/pull/66

- Restricted GitHub main OIDC trust; one SSM document on one EC2 instance; temporary credentials, no extra inbound SSH.
- SSM runs the reviewed SHA as deploy, validates inputs and clean Git checkout, serializes jobs with a host lock, and prevents activation without a private marker created during the restore/cutover.
- Existing Contabo workflow remains active while AWS validates candidates only. AWS_DEPLOY_ENABLED must remain false until the fresh production copy and operational cutover are ready.
- Four command/input/polling/error tests and CloudFormation/shell validation passed locally. PR CI 39423191289 succeeded on 1b97a9a5d24277b844059f2f9d02660eca43f5fe; merged main revision fd57c975b46923efcd3584e25b369b65363a36c9. Main workflow 39423923671 passed all tests and Contabo deployment, but AWS authentication rejected the legacy OIDC subject. GitHub API confirmed this repository uses immutable owner/repository IDs. Correction is tracked in PR 67; no AWS services or database were activated by that failed attempt.
- Deployment stack nuviamy-github-deployment created and termination-protected. Six IAM policy simulation checks passed: only the selected instance and fixed document admit SendCommand; a different instance, AWS-RunShellScript, document modification and IAM user creation are denied. Exact main/audience trust verified. This is policy simulation, separate from the pending real workflow proof.
- GitHub variables configured with AWS_DEPLOY_ENABLED=false; no static AWS keys created and no changes to SSH ingress or legacy deployment secrets.

## Remaining cutover

Fresh production DB/document copy under a write freeze, storage/digest/role checks, production encrypted backup/restore proof, single-writer/job transition, and DNS/old-origin routing coordination. Do not reuse the sanitized rehearsal database. After new AWS writes begin, reverting to the stale Contabo database requires reconciliation.

Follow-up PR: https://github.com/richard9106/django-analytics-dashboard/pull/67. Exact immutable prefix: repo:richard9106@114283158/django-analytics-dashboard@1371998866. The corrected trust retains exact main/audience matching.

## Final verification

- PR 67 passed CI 39425116981 on 9a9e92455d3a5e025bdd259b5b37f1bae884c169. Correction merged as 533fc73149bd44b788ad0deb149588b2b1ba8b13; PR and merge trees are the reviewed final implementation.
- IAM update changed only the existing deployment role, without replacement. Exact immutable main/audience trust and all six permission simulations passed afterward.
- Main workflow 39425673934 succeeded: complete test job, legacy Contabo deployment, and real GitHub OIDC/STS/account-check/SSM validation on AWS.
- Actual SSM command 03e58f6d-f541-4762-860f-1683914f96a0 returned success/0 and confirmed candidate validation without database, service or timer changes.
- AWS checkout is clean at 533fc73149bd44b788ad0deb149588b2b1ba8b13. Production activation marker remains absent and no containers are running. Source public health is 200; direct AWS HTTPS is intentionally 503 with certificate verification 0.
- This closes Git/TLS preparation. It does not establish the production data copy, production Deploy mode, backup restoration of the final copy, DNS cutover or clinical/HIPAA approval.
