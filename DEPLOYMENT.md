# Deployment

Production runs on a VPS with Docker Compose for Django and PostgreSQL. Nginx stays installed on the host and proxies traffic to Gunicorn on `127.0.0.1:8000`.

Production domain: `nuviamy.com`.

## VPS Setup

Clone the repository on the VPS and create a production `.env` file in the project root:

```env
DJANGO_ENVIRONMENT=production
DJANGO_SECRET_KEY=REPLACE_WITH_A_RANDOM_SECRET_OF_AT_LEAST_50_CHARACTERS
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=nuviamy.com,www.nuviamy.com,YOUR_SERVER_IP
DJANGO_CSRF_TRUSTED_ORIGINS=https://nuviamy.com,https://www.nuviamy.com
SENTRY_DSN=
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.05

POSTGRES_DB=dashboard
POSTGRES_USER=dashboard_user
POSTGRES_PASSWORD=change-me-to-a-strong-password
POSTGRES_HOST=db
POSTGRES_PORT=5432

FIELD_ENCRYPTION_KEY=REPLACE_WITH_A_FERNET_KEY

SECURE_SSL_REDIRECT=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=true
SECURE_HSTS_PRELOAD=true

DJANGO_STORAGE_BACKEND=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_STORAGE_BUCKET_NAME=nuviamy
AWS_S3_ENDPOINT_URL=https://<account-id>.us.r2.cloudflarestorage.com
AWS_S3_REGION_NAME=auto

GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_OAUTH_REDIRECT_URI=https://nuviamy.com/settings/integrations/google/callback/

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-brevo-login-email
EMAIL_HOST_PASSWORD=your-brevo-smtp-key
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
DEFAULT_FROM_EMAIL=NuviaMy <noreply@nuviamy.com>
SUPPORT_EMAIL=support@nuviamy.com
BACKUP_ENCRYPTION_PASSPHRASE=
BACKUP_R2_PREFIX=backups/postgres

STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_SOLO_MONTHLY=
STRIPE_PRICE_SOLO_YEARLY=
STRIPE_PRICE_GROUP_MONTHLY=
STRIPE_PRICE_GROUP_YEARLY=
STRIPE_PRICE_CLINIC_MONTHLY=
STRIPE_PRICE_CLINIC_YEARLY=
```

Replace the secret placeholders before starting. Production refuses to start
with DEBUG enabled, a weak Django secret, missing or placeholder database
credentials, SQLite, missing/wildcard allowed hosts, HTTP CSRF origins,
disabled HTTPS/cookie controls, no HSTS, or a missing/invalid Fernet key.
Docker Compose always selects the production environment and requires the
three secrets to be present. Summernote attachment uploads are disabled because
they lack Practice/client authorization; use the Documents workspace for uploads. Local non-Docker development can use
`DJANGO_ENVIRONMENT=development` and SQLite as described in `.env.example`.

Generate a new Django secret and Fernet key with a secure password/secret
manager. Preserve the existing `FIELD_ENCRYPTION_KEY` on an existing deployment:
replacing it without a token migration makes stored OAuth tokens unreadable.
Store production secrets outside Git and never copy the public CI fixtures.

For a new installation, build and validate before starting the app:

```bash
docker compose build web
docker compose up -d db
docker compose run --rm --no-deps web python manage.py check --deploy --fail-level WARNING
docker compose run --rm --no-deps web python manage.py migrate --noinput
docker compose up -d --no-build
docker compose exec web python manage.py collectstatic --noinput
docker compose exec web python manage.py createsuperuser
```

Routine releases use `.github/workflows/deploy.yml`. Pull requests run the full
suite against an isolated PostgreSQL 16 database, dependency consistency checks,
migration consistency checks, and production checks that fail on warnings.
Deployment runs only after the test job succeeds on `main`. The VPS checks out
the exact tested commit, builds the candidate, and validates the real production
configuration before migrations and service replacement. Running workflows are
not canceled midway through deployment. A failed candidate preflight leaves the
existing service running, but its working checkout/build tag may already have
advanced; review the failed run before retrying. This is not automatic rollback
for a failed migration or service replacement.

## Nginx

Use the production domain as `server_name`:

```nginx
server {
    listen 80;
    server_name nuviamy.com www.nuviamy.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Validate and reload Nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## GitHub Secrets

The deploy workflow requires these repository secrets:

```text
VPS_HOST=YOUR_SERVER_IP
VPS_USER=your-vps-user
VPS_SSH_KEY=private-key-with-access-to-the-vps
VPS_APP_DIR=/absolute/path/to/django-analytics-dashboard
VPS_PORT=22
```

After setup, every push to `main` deploys the latest code, rebuilds containers, runs migrations, and collects static files.

## Capacity Baseline

The current VPS baseline is approximately:

- 6 vCPU.
- 11 GiB RAM and 4 GiB swap.
- 193 GiB disk with about 171 GiB available at the last review.
- Gunicorn configured for 4 workers and 2 threads.
- PostgreSQL `max_connections=100`.
- Nginx `worker_connections=768`.

This is a reasonable starting point for a private beta and tens of concurrently active interactive users. It is not a guarantee for a large public launch. Capacity should be validated with an authenticated load test using realistic dashboard, calendar, portal, document, and billing traffic.

Scale when sustained CPU exceeds roughly 70%, memory pressure/swap appears, database connections approach the configured limit, or p95 request latency exceeds the product target. The next production steps are a managed PostgreSQL instance, Redis/cache or queue workers where needed, centralized monitoring, and a second web replica behind a load balancer.

## Error And Uptime Monitoring

Create a Django project in Sentry and set these VPS variables to enable application error reporting:

```env
SENTRY_DSN=https://...
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.05
```

Sentry is disabled when `SENTRY_DSN` is empty and is configured with `send_default_pii=false`. Use UptimeRobot, Better Uptime, or Uptime Kuma separately for an external HTTP check of `https://nuviamy.com/health/` or the public homepage. The staff-only in-app view is available at `/staff/monitoring/`.

## PostgreSQL Backups

The repository includes:

- `ops/backup_postgres.sh`: creates a restricted PostgreSQL custom-format dump and keeps the last 14 days by default.
- The same script encrypts the dump with GPG AES-256 and uploads it to the configured private R2 bucket under `BACKUP_R2_PREFIX`.
- `ops/verify_postgres_backup.sh`: restores a dump into a temporary database, checks migrations, and removes the temporary database.
- `ops/restore_r2_backup_check.sh`: downloads, decrypts, and verifies an encrypted R2 backup without modifying production data.
- `ops/systemd/nuviamy-postgres-backup.service` and `.timer`: daily backup at 03:30 UTC with persistence after reboot.

Install the timer on the VPS after the repository is deployed:

```bash
sudo cp ops/systemd/nuviamy-postgres-backup.service /etc/systemd/system/
sudo cp ops/systemd/nuviamy-postgres-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nuviamy-postgres-backup.timer
sudo systemctl start nuviamy-postgres-backup.service
systemctl status nuviamy-postgres-backup.timer --no-pager
```

Verify the newest backup without modifying the production database:

```bash
LATEST_BACKUP=$(ls -t /home/deploy/backups/nuviamy/postgres/nuviamy-*.dump | head -1)
/home/deploy/apps/django-analytics-dashboard/ops/verify_postgres_backup.sh "$LATEST_BACKUP"
```

The local dump is retained for fast recovery and the encrypted R2 object is the offsite copy. Keep `BACKUP_ENCRYPTION_PASSPHRASE` outside Git and back it up separately; without it, encrypted R2 backups cannot be restored.

## Brevo SMTP

In Brevo, create an SMTP key under **Settings > SMTP & API > SMTP**. Use the SMTP key, not the Brevo API key or account password. Also verify the sender/domain used by `DEFAULT_FROM_EMAIL`.

Production values:

```env
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-brevo-login-email
EMAIL_HOST_PASSWORD=your-brevo-smtp-key
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
DEFAULT_FROM_EMAIL=NuviaMy <noreply@nuviamy.com>

GUNICORN_WORKERS=4
GUNICORN_THREADS=2
GUNICORN_TIMEOUT=120
```

After changing the VPS `.env`, restart the web container:

```bash
docker compose up -d --build web
docker compose exec -T web python manage.py check
```

These HTTPS settings assume that the site is served exclusively through HTTPS by Nginx. Do not enable HSTS/preload before confirming that every production subdomain is HTTPS-only.

Password reset emails use this SMTP configuration. Team invitations use connected Gmail OAuth first; Brevo is the fallback when Gmail sending is not connected.

## Stripe Setup

Create Stripe products and recurring prices in test mode first:

- Solo Therapist: monthly and yearly prices.
- Group Practice: monthly and yearly prices.
- Clinic: monthly and yearly prices.

Copy the `price_...` IDs into the matching `STRIPE_PRICE_*` variables.

Create a webhook endpoint:

```text
https://nuviamy.com/billing/stripe/webhook/
```

Required events:

```text
checkout.session.completed
checkout.session.async_payment_succeeded
customer.subscription.updated
customer.subscription.deleted
invoice.payment_failed
```

Copy the endpoint signing secret into `STRIPE_WEBHOOK_SECRET`.

## Stripe Connect For Practice Payments

Stripe Connect must be enabled for the NuviaMy Stripe platform before practices can receive client invoice payments. In the Stripe Dashboard:

1. Enable Stripe Connect and complete the platform profile.
2. Use the same mode as `STRIPE_SECRET_KEY` (test or live).
3. Make sure the platform can create Express connected accounts with `card_payments` and `transfers` capabilities.
4. Confirm the platform country and connected-account country support the requested capabilities.

Practice owners or admins finish onboarding from **Profile Settings > Client payments**. Stripe hosts the legal, identity, and bank-account collection flow. NuviaMy stores only the connected account ID and capability status.

Client invoice payments use destination transfers to the practice's connected account. They are separate from the NuviaMy SaaS subscription and do not use the practice's SaaS Stripe customer.

## Google OAuth Setup

Use this redirect URI in Google Cloud Console:

```text
https://nuviamy.com/settings/integrations/google/callback/
```

Gmail, Calendar, and Drive scopes are requested through one Google connection. Tokens are stored encrypted, so `FIELD_ENCRYPTION_KEY` must be stable across deploys.

## Appointment Reminders

The reminder command is:

```bash
python manage.py send_appointment_reminders
```

Production can run it with a systemd timer every 15 minutes. Gmail must be connected for delivery.

## Staff MFA and session operations

Staff, practice owners/admins, and Django administrators must enroll an authenticator
at their next sign-in. Existing unstamped sessions are revoked by this release.
Use synthetic accounts in staging to rehearse enrollment before onboarding a clinic.
Client portal accounts retain password-based sign-in. Every authenticated account
has a 15-minute idle timeout and an 8-hour absolute limit; pending staff MFA expires
10 minutes after password authentication. Export, team changes, and profile changes
require authentication within the last 5 minutes.

Enrollment and authenticator replacement require the current password and a fresh
TOTP. Ten random recovery codes are displayed once; store them securely outside
NuviaMy. Codes are stored hashed and consumed atomically. Secrets and temporarily
displayed codes are Fernet-encrypted, including in development: configure a valid
`FIELD_ENCRYPTION_KEY`. Preserve this key with encrypted database backups; losing
it prevents MFA verification and encrypted integration-token recovery. Do not
replace the key without a planned data/key migration.

The Account security page permits new recovery codes, authenticator replacement,
and revocation of other sessions. Both factors are required for staff security
actions. Five invalid factor/password attempts lock that account's MFA for 15
minutes. Public password/reset and MFA endpoints also have PostgreSQL-backed IP
limits; the host proxy must append the real source IP to `X-Forwarded-For`, and
port 8000 must remain restricted to localhost as configured in Compose.

For a lost authenticator **and** lost recovery codes, independently verify identity
through the clinic's approved support procedure and record a ticket reference.
An authorized server operator may then run:

```bash
docker compose exec -T web python manage.py reset_staff_mfa USERNAME --reason VERIFIED_TICKET_REFERENCE
```

This removes enrollment and recovery codes, revokes every session, and writes a
practice audit event when a practice is associated. It does not change the
password. Password reset alone never removes MFA. Platform administrators without
a practice currently require a separate operator incident/change record because
the existing audit model requires a practice; do not treat this as a complete audit
trail. No support reset is exposed through a public endpoint or Django admin.

Include these maintenance commands in the approved daily server operations job:

```bash
docker compose exec -T web python manage.py clearsessions
docker compose exec -T web python manage.py clear_security_rate_limits
```

Expired rate-limit buckets reset on use; deletion only removes expired buckets.
The browser watchdog hides protected content on timeout and propagates logout
across tabs. A browser may discard unsaved edits when a session expires. TOTP is
not phishing-resistant; evaluate WebAuthn and stronger administrative access as
part of the risk assessment. These controls do not establish clinical readiness.

Static files and their manifest are generated during the Docker build and packaged
in the image. The Compose web service has no staticfiles volume: running
collectstatic in a disposable container does not update the running service.
CI verifies hashed assets and the login page in a fresh container with DEBUG=false;
deployment checks both application health and the session JavaScript. For an
operational repair of an already running image, collectstatic must run through
`docker compose exec -T web`, followed by a restart; the committed image build is
the durable deployment mechanism.
