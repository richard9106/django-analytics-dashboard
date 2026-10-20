# AWS isolated restoration rehearsal — 20 October 2026

## Code and deployment

- PR 65: https://github.com/richard9106/django-analytics-dashboard/pull/65
- Tested candidate: 5cb6aff5a1c69dbbfcee5f630832740129a24c96.
- Merged/deployed main: c8c4c9a64441d5ab47cc8dbd969acd28acd85fef.
- Candidate and main Git trees identical: a568b554c4973e6b660e26a88ce381550724cbc8.
- Local full suite: 605 passing; after the additional restored-session test, all 10
  focused storage/isolation tests passed. CI full suite: 606 passing.
- PR workflow 39416901702 and main test/deploy workflow 39418321383 succeeded.
- Native S3 is opt-in; existing production R2 settings and live payment settings
  were preserved. Production health and both existing R2 document hashes verified.

## Actual restore and safety checks

1. Captured a fresh read-only REPEATABLE READ database checkpoint, held its exported
   PostgreSQL snapshot while pg_dump ran, and collected matching model counts and
   clinical signature digests. Original database was not paused or modified.
2. Encrypted the original archive before it left the source. Authenticated CMS
   decryption and PGDMP archive header checked locally. Recipient private key stayed
   local. App/Fernet keys preserved; rehearsal DB passwords generated separately.
3. Captured two documents with authenticated encrypted manifest and SHA256 checks;
   document IDs/storage keys matched the database checkpoint. Original source files
   were neither edited nor deleted. Capture is not an atomic cross-service snapshot;
   final cutover still requires a consistent frozen final copy and file reconciliation.
4. Built the committed image before supplying secrets/data. Private env files,
   restored media and backup archives excluded from image context. Runtime configs
   were outside the checkout/build context; private fields were not printed.
5. Restored into a verified empty *_rehearsal PostgreSQL 16 database on encrypted
   EBS. Dedicated bootstrap/migration/runtime roles and all nine immutable clinical
   and audit guard triggers verified. Migrations required no schema changes.
6. Internal-only Docker network, disabled metadata credentials and blank external
   keys applied to runtime/migration services. Dummy email, no source R2 access,
   no Sentry and no reminder/backup timers. Removed restored sessions and disconnected
   all three copied integrations without sending requests or revoking source tokens.
7. Source/restored model counts matched (except intentionally cleared sessions).
   One signed note retained its exact valid digest; zero source addenda existed.
   Both restored document SHA256 hashes matched. Fernet key preservation checked
   using a neutral encrypted probe. A direct SQL modification of the signed note
   was rejected. External socket connections and IMDS access were blocked.
8. Owner request smoke tests returned 200 for dashboard, appointments, clients,
   clinical notes and documents, within a transaction rolled back afterward. The
   actual Gunicorn process returned 200 for health and login from inside its private
   container. No public Nginx proxy or DNS switch enabled.
9. A separate disposable container without restored data successfully saved/read
   a neutral object through Django's native S3 backend and instance-role credentials;
   signed HTTPS URL checked without printing it. No static keys used. Synthetic
   object versions removed by the authorized operator. This network-enabled probe
   did not join or weaken the internal rehearsal runtime network.
10. Ran the updated backup script against the rehearsal: pg_dump -> GPG AES256 with
    passphrase on a private descriptor -> separate S3 backup bucket using instance
    role. Retrieved it, verified S3 encryption and GPG integrity, restored into a
    second empty temporary database, and compared all 52 table counts successfully.
    The first count verifier needed chunking for PostgreSQL's function argument
    limit; it was corrected and the complete restore repeated successfully. The
    temporary recovery database was dropped; primary rehearsal remained intact.
11. Rehearsal web and DB stopped cleanly after verification. Its private configuration,
    encrypted disk/volume and encrypted offsite backup remain for review. No standby
    copy sends traffic or becomes a second production writer.
12. After release, original production health OK, R2 files readable with unchanged
    hashes, email two-step enabled, Stripe live retained, MIGRATION_REHEARSAL false.

Detailed manifests, encrypted archives, private diagnostics and proof JSON files
are outside Git under the private NuviaMy recovery/operator directories. This report
contains no credentials, patient content, private keys or signed URLs.

## Remaining cutover work

- Keep the sanitized rehearsal separate; never promote its cleared tokens/sessions
  as production. Use a fresh source checkpoint and source-file reconciliation.
- Prepare reviewed native S3 production environment and upload real documents with
  preserved keys; test the separate production backup schedule and failure alerts.
- Prepare TLS on destination, verify SMTP authentication/delivery (including the new
  IP allowlist if enforced by Brevo), and rehearse Stripe webhook arrival/idempotency.
- Plan write freeze, single writer/job scheduler, GitHub deployment secret migration,
  DNS change and rollback before accepting new writes. No such cutover occurred here.
- The measured restore proves recovery feasibility; no contractual RPO/RTO or general
  HIPAA certification is asserted. Clinical/security/retention review remains separate.
