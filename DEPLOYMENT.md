# Deployment

Production runs on a VPS with Docker Compose for Django and PostgreSQL. Nginx stays installed on the host and proxies traffic to Gunicorn on `127.0.0.1:8000`.

Production domain: `nuviamy.com`.

## VPS Setup

Clone the repository on the VPS and create a production `.env` file in the project root:

```env
DJANGO_SECRET_KEY=change-me-to-a-long-random-secret
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=nuviamy.com,www.nuviamy.com,YOUR_SERVER_IP
DJANGO_CSRF_TRUSTED_ORIGINS=https://nuviamy.com,https://www.nuviamy.com,http://YOUR_SERVER_IP

POSTGRES_DB=dashboard
POSTGRES_USER=dashboard_user
POSTGRES_PASSWORD=change-me-to-a-strong-password
POSTGRES_HOST=db
POSTGRES_PORT=5432

FIELD_ENCRYPTION_KEY=

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

Start the app:

```bash
docker compose up -d --build
docker compose exec web python manage.py migrate --noinput
docker compose exec web python manage.py collectstatic --noinput
docker compose exec web python manage.py createsuperuser
```

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
