# Production cutover — 20 October 2026

Status: operator confirmed the DNS change; root and www now resolve to AWS 34.227.127.145 and return HTTPS health 200 with valid certificates. Contabo is frozen and returns maintenance 503. Do not restart its app or timers: AWS may now accept writes. Any rollback to the source requires reconciliation.

## Verified before activation

- Main 533fc73149bd44b788ad0deb149588b2b1ba8b13 passed complete CI and GitHub OIDC/SSM validation (39425673934). Production activated through the same fixed document at that exact reviewed SHA.
- Coordinated DNS change with the operator before pausing the source. Public A records for root and www were 193.46.243.105, TTL approximately 300 seconds; no AAAA observed.
- Temporarily disabled the Git workflow, put NuviaMy in source Nginx maintenance, and stopped the source web service, backup/reminder timers and active jobs. Source DB remains protected and preserved. No unrelated applications changed.
- Captured an authenticated encrypted database checkpoint from a held read-only exported snapshot and an encrypted document manifest while all source writers were stopped. CMS private recovery key remained on the operator computer.
- Restored into a verified empty AWS production database, separate from the sanitized rehearsal. Source application/encryption/integration credentials preserved; new PostgreSQL passwords and separate bootstrap/migration/runtime roles used.
- All 47 managed model counts matched, including original sessions/integration rows. The signed note digest matched and an attempted transactionally rolled-back signed content change was rejected. Two document keys/bytes/hash values matched after private native S3 upload and readback.
- Captured a fresh AES256/GPG backup through the host role to the separate S3 backup bucket; retrieved and authenticated it, actually restored a second empty database, compared all 52 SQL table counts, then removed only that disposable recovery DB.

## Active destination

- Elastic IP 34.227.127.145. Existing independent AWS certificate and tested Certbot renewal retained. Nginx now proxies to the verified app, without the preflight noindex header.
- Direct HTTPS requests with explicit DNS resolution: health, login, homepage and security-session.js all 200; TLS certificate validation 0. An unsigned Stripe webhook was rejected with 400 before processing; this is endpoint/signature readiness, not proof of a new live payment or post-DNS delivery.
- Original Stripe live secrets and Google credentials preserved; no new charge or outbound client message created as part of verification. AWS email delivery was previously confirmed by the operator.
- Private activation marker created only after restoration and backup proof. AWS_DEPLOY_ENABLED=true, Git workflow enabled again. Removed only the reversible legacy VPS_HOST GitHub secret to prevent older workflow reruns reconnecting the stale source; remaining legacy key/app metadata retained. Old host was 193.46.243.105.
- Source timers disabled and source web stopped. AWS encrypted backup timer active. AWS reminder timer enabled after operator DNS confirmation and successful public resolution/HTTPS checks. Source reminder/backup timers remain disabled.

## Pending user action and follow-up

Change Cloudflare root and www A records to 34.227.127.145, DNS-only. Then verify authoritative/public resolution and live login/document/billing routes; enable reminders on AWS only, observe Stripe retry/delivery, and validate a subsequent GitHub production deployment. Some cached old-origin requests may see maintenance for the remaining TTL.

Private evidence and encrypted final recovery artifacts: /home/richard/Documents/Personal/NuviaMy-Recovery/aws-cutover-20261020 (0700, files 0600). Do not commit these materials, `.env`, raw data, recovery keys, or SSM production output.

The origin migration and AWS BAA do not themselves establish clinical validation or full HIPAA compliance. The protected source copy remains for a deliberately managed rollback/retirement window; do not reactivate stale data or erase unrelated VPS services.

## Post-DNS verification

- Operator confirmed root/www DNS edits. Both names resolve to 34.227.127.145, public HTTPS health 200 and TLS verification 0.
- AWS reminder, encrypted backup and Certbot timers active; source NuviaMy web remains stopped and its timers inactive.
- Public login and static asset checks performed. Live Stripe endpoint remains enabled at the unchanged URL; read-only Stripe inspection found zero new events and zero pending webhook events since the frozen checkpoint. No charge was created; post-migration live payment delivery is not claimed from an empty event window.
- GitHub full production deployment dispatched at reviewed main SHA, run 39430159662. Completed successfully: full tests and actual AWS Deploy succeeded; legacy source deployment was skipped.

## Migration completed

Full GitHub production run 39430159662 succeeded at 533fc73149bd44b788ad0deb149588b2b1ba8b13. Real SSM Deploy command succeeded, followed by public root/www health, login and static checks: all 200 from 34.227.127.145 with valid TLS. Source web remains stopped and source timers inactive. AWS is the only active NuviaMy application origin, with native S3 documents, encrypted scheduled backups, reminders and certificate renewal enabled. Retain the source copy as protected historical recovery material; it must not be reactivated without reconciliation of AWS writes.
