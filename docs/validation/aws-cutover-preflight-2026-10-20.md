# AWS cutover preflight — 20 October 2026

Status: preparation only. Public DNS, Contabo service, GitHub deployment target and production timers have not been changed.

## Completed

- TLS certificate and key for nuviamy.com copied over encrypted connections from the current origin, installed root-only on AWS; temporary deploy-user copy removed. Nginx configuration tested and reloaded.
- HTTPS tested using curl --resolve, without DNS changes: certificate verification succeeds; AWS intentionally returns maintenance (503). No application records are served publicly.
- Separate production Git checkout pinned to reviewed/deployed c8c4c9a64441d5ab47cc8dbd969acd28acd85fef; rehearsal archive/database are not promoted.
- Production candidate environment stored privately outside the build context, with native S3, separate backup bucket/prefix, instance role, retained application encryption keys, separate new database passwords, email verification required, two Gunicorn workers. Candidate is not activated.
- Initial SMTP preflight rejected by Brevo with code 525. After the operator authorized AWS IP 34.227.127.145, STARTTLS/authentication succeeded. One technical test message sent only to marleswebinfo@gmail.com was accepted by SMTP; operator confirmed inbox delivery on 20 October 2026. Current Contabo delivery is unaffected.

- Production image built successfully; Compose configuration and Django production deployment checks passed. Git checkout is clean on main at the reviewed SHA. Private environment and rehearsal media are absent from the image. A one-off check created the production network/empty volume, but no database or web service is running.

## Required before the cut

1. Complete SMTP verification and least-privilege production database setup. Image/configuration deployment checks have passed; data/role verification awaits the fresh restore.
2. Git transition prepared and verified through GitHub OIDC/SSM (main workflow 39425673934). AWS_DEPLOY_ENABLED remains false, existing SSH secrets still target Contabo, and AWS SSH ingress is unchanged. Switch the variable and private activation marker only during the coordinated production cutover.
3. TLS preparation complete: AWS has an independent certificate, active Certbot timer and successful renewal dry-run/deploy hook. ACME challenges currently forward from Contabo; AWS serves its own webroot after DNS changes. Keep that path functional through propagation.
4. Freeze only NuviaMy writers on Contabo, including reminders and application writes. Webhooks must receive retryable errors or be forwarded to the active writer; never acknowledge and discard events.
5. Capture and restore a fresh production database and documents, preserving source integration credentials. Compare counts, signed-note digests and document hashes. Use a separate production Compose project/volume; never reuse the sanitized rehearsal database.
6. Upload private production documents to S3, prove native retrieval, run deploy/role checks, and prove an encrypted production backup can be restored. Enable timers only on the new active writer.
7. Validate the final AWS origin over HTTPS, then coordinate DNS and old-origin forwarding to avoid simultaneous writers. Verify login/email codes, note signatures, documents, live billing status and webhook handling without a new charge.
8. Keep Contabo NuviaMy data protected for rollback. The VPS also hosts unrelated applications; do not stop/delete the VPS or unrelated services. After new writes occur on AWS, rollback requires reconciliation; the old database must not simply be reactivated.

AWS BAA coverage is account/service dependent and does not by itself establish HIPAA compliance or clinical approval.
