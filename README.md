# NuviaMy

NuviaMy is a Django-based therapy practice management SaaS for solo therapists, psychologists, and multi-provider clinics. The project is built as a realistic portfolio application focused on secure client management, scheduling, clinical workflows, billing, subscriptions, document storage, Google integrations, and a client portal.

## Product Vision

NuviaMy helps mental health professionals manage their practice from one calm, secure workspace:

- Manage solo practices and multi-therapist clinics.
- Track clients, appointments, sessions, notes, treatment plans, invoices, subscriptions, documents, and client requests.
- Provide clients with a portal for appointments, documents, intake, and practice communication.
- Model HIPAA-aware architecture and security practices for a realistic healthcare SaaS portfolio project.

This project is educational and portfolio-focused. It is designed with HIPAA-aware principles, but it is not certified for real clinical use.

## Implemented Product Areas

The current version includes these working modules:

- `accounts`: signup, email-based login/logout, role/profile model, practice ownership setup, client password-change enforcement.
- `practices`: practice and therapist profile models, tenant scoping, integration settings, encrypted Google OAuth tokens.
- `clients`: patient directory, create/edit/delete popups, practice-scoped client records, add note from client, assign package from client, create appointment popup from client workspace.
- `appointments`: calendar view, Monday-start calendar, create/edit/delete popups, today highlighting, tenant-scoped appointment scheduling, availability validation, weekly recurrence, Google Calendar sync, Gmail reminder command.
- `clinical`: clinical notes, diagnosis records, treatment plans, linked treatment progress, lock note behavior, review-due workflow.
- `billing`: invoices, package invoices, superbills, automatic invoice numbering, prepaid service packages, package usage tracking, insurance payer/rate settings, Stripe subscription checkout, 15-day trial, webhooks, practice subscription persistence.
- `documents`: client document upload/list/download/delete, file metadata, tenant-scoped downloads, Google Drive export, local storage with Cloudflare R2 production support.
- `portal`: client-facing dashboard, portal access accounts, enforced temporary password change, visible documents, appointment change requests, intake packet completion.
- `intake`: practice intake templates, client packet assignment, client portal submission workflow.
- `requests`: practice-side inbox for client portal requests and appointment change requests.
- `notifications`: appointment reminder model and Gmail-based reminder delivery command.
- `audit`: audit logging for sensitive workflows such as auth, documents, clinical notes, billing, portal, intake, and integrations.
- `dashboard`: operational practice dashboard with today appointments, tasks, billing summary, recent invoices, quick actions, first-steps panel, and guided onboarding tour after Stripe checkout.
- `settings`: session package templates, insurance settings, availability, portal access, Google integrations, Google workspace.
- `telehealth`: telehealth room model reserved for future provider integration.
- `admin`: Django admin registration for core domain models, including subscriptions.

## Current Workflow Summary

### Dashboard

- Top action bar with quick create actions and profile menu.
- Practice metrics: monthly revenue, active patients, today's sessions, pending tasks.
- Today appointments panel.
- Tasks panel from notes, invoices, notifications, portal requests, and treatment plan reviews.
- Recent billing activity.
- First-steps setup panel for clients, availability, appointments, and portal access.
- Guided onboarding tour launched from Stripe success via `/dashboard/?tour=1` and repeatable from the dashboard.

### Clients

- `My patients` grid with four desktop columns, two tablet columns, one mobile column.
- Create/edit/delete client using popups.
- Add clinical note directly from a client card.
- Assign a prepaid session package directly from a client card.
- Create appointments from the clients workspace with a popup.
- Client cards are practice-scoped.

### Appointments

- Calendar page with Monday-first weeks.
- Current day highlighted.
- Day-level `+` opens appointment creation popup and pre-fills date/time.
- Existing appointment opens edit popup.
- Delete appointment from edit popup.
- Availability rules can be configured under Settings.
- Weekly recurring appointments can be generated at creation time.
- Google Calendar sync metadata is tracked and can be repaired/synced.
- Gmail-based appointment reminders can be sent through the management command.
- Fallback create/edit pages remain available.

### Clinical Notes

- Notes workspace with list and popups.
- Notes link to client, therapist, and optional appointment.
- Notes can link to treatment plans and include treatment progress.
- `Lock note` marks a note as final and sets `locked_at`.
- Diagnosis and treatment plan records are practice-scoped.
- Treatment plans support review dates and review completion.

### Billing And Packages

- Billing workspace with invoices and prepaid session packages.
- Session package templates configured under Settings.
- Assign package to client from Clients page.
- Create invoices against either appointments or packages.
- Invoice number auto-generates when blank:

```text
PKG-{package_id}-{YYYYMMDD}-{sequence}
```

- Selecting a package in invoice form fills client and amount.
- Selecting an appointment fills client.
- Package usage tracks sessions used and remaining.
- Expired, completed, or refunded packages cannot be used for sessions.
- Printable invoices and superbills are available.
- Insurance settings support common payer templates and practice-specific reimbursement rates.
- Stripe Checkout creates SaaS subscriptions for Solo, Group, and Clinic plans.
- New signups are routed to Stripe Checkout with a 15-day free trial and card collection.
- Stripe webhooks update local `PracticeSubscription` records for checkout completion, subscription updates/deletions, and failed payments.

### Documents

- Upload client documents from `/documents/`.
- Documents are scoped to practice and client.
- Metadata stored in DB: original filename, content type, file size, portal visibility flag.
- Downloads go through Django authorization checks.
- Local `MEDIA_ROOT` storage works now.
- Cloudflare R2 support is configured through env vars but must be enabled in production.
- Documents can be exported to Google Drive when Google is connected.

### Client Portal And Intake

- Practice users can create client portal access accounts.
- Client users are restricted to `/portal/` and cannot access internal practice pages.
- Temporary-password users must change password before using the portal.
- Clients can view upcoming appointments and visible documents.
- Clients can submit appointment change requests.
- Practice users manage portal requests from the request inbox.
- Intake templates can be created and assigned to clients.
- Clients can complete assigned intake packets from the portal.

### Google Integrations

- A single Google OAuth connection supports Gmail, Calendar, and Drive scopes.
- OAuth tokens are encrypted at rest using Fernet through `FIELD_ENCRYPTION_KEY`.
- Gmail is used for appointment reminder delivery when connected.
- Google Calendar sync mirrors appointment records to Google.
- Google Drive export uploads authorized client documents.
- NuviaMy remains the source of truth; Google is treated as an external mirror/export target.

### Stripe Subscriptions

- Public pricing page supports Solo, Group, and Clinic plans.
- Monthly and yearly Stripe Price IDs are configured through environment variables.
- Signup preserves selected plan/period and redirects to Checkout after account creation.
- Checkout uses a 15-day trial with card collection.
- Checkout success routes users to the dashboard guided tour.
- Webhook endpoint: `/billing/stripe/webhook/`.

Required webhook events:

```text
checkout.session.completed
customer.subscription.updated
customer.subscription.deleted
invoice.payment_failed
```

## Storage

By default, uploaded documents use local filesystem storage:

```env
DJANGO_STORAGE_BACKEND=
```

For Cloudflare R2, production should set:

```env
DJANGO_STORAGE_BACKEND=r2
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_STORAGE_BUCKET_NAME=nuviamy
AWS_S3_ENDPOINT_URL=https://<account-id>.us.r2.cloudflarestorage.com
AWS_S3_REGION_NAME=auto
```

Do not commit R2 credentials. `.env` and `media/` are ignored by Git.

## Payments Configuration

Stripe settings are read from environment variables and must not be committed:

```env
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

The test card for Stripe test mode is:

```text
4242 4242 4242 4242
Any future expiration date
Any CVC
Any ZIP
```

## Next Recommended Work

- Add SaaS subscription management screen for practice owners.
- Add Stripe Customer Portal for card changes, invoices, and cancellation.
- Enforce plan limits for Solo, Group, and Clinic users.
- Add client portal payments for therapy invoices, separate from SaaS subscription billing.
- Add document upload from the client portal.
- Add recurring appointment series editing/cancellation controls.
- Add Google sync issue dashboard and reconnect state.
- Add Dropbox OAuth/export support.
- Define no-show/cancellation rules for package usage.
- Rotate any credentials that were exposed outside the environment.

## Security And Compliance Direction

NuviaMy should be built with healthcare-grade habits from the beginning:

- Every sensitive object belongs to a `Practice`.
- Users must only access data from their own practice.
- Clinical notes should never be written to logs.
- HTTPS is required in production.
- Secrets must live in environment variables, never in Git.
- Stripe, Google, R2, and field encryption secrets must be set through `.env` or VPS/GitHub secret management.
- Client users must only access portal routes.
- OAuth tokens are encrypted at rest.
- Production services that handle PHI should support a Business Associate Agreement (BAA).
- Audit logging is implemented for many sensitive events, but compliance review is still required before real clinical use.

## Design System

NuviaMy uses a calm, modern, human visual language for mental health professionals. The design system is based on `nuvia_brand_ui_system.html`.

### Brand

- Product name: `NuviaMy`
- Tone: calm, professional, modern, human, and trustworthy.
- Avoid visual clichés such as medical crosses, literal brains, or overly clinical hospital styling.

### Colors

- Iris 600: `#7052D9` as the primary brand color.
- Aqua 500: `#14B8A6` for positive/supportive accents.
- Coral 500: `#F36F56` for editorial or attention accents.
- Slate 800: `#1F2937` for primary text.
- Slate 50: `#F8F9FB` for app backgrounds.

### Typography

- UI font: `Manrope`.
- Editorial accent: `Lora Italic`.
- Body text baseline: `16px`.
- Small text: `14px`.
- Hero/display text: `56px` to `64px` on large screens.

### Layout Rules

- Desktop grid: 12 columns, 24px gap, max width 1280px.
- Tablet grid: 8 columns, 20px gap, 24px page padding.
- Mobile grid: 4 columns, 16px gap, 16px page padding.
- Expanded sidebar: 248px.
- Compact sidebar: 72px.
- Mobile internal navigation uses a sticky top menu with a collapsible primary navigation panel.
- Topbar height: 64px to 72px.
- Card radius: 16px.
- Card padding: 20px to 24px.
- Button height: 44px to 48px; large buttons 52px.
- Inputs: 44px to 48px tall with 10px radius.
- Spacing scale: 4, 8, 12, 16, 24, 32, 48, 64.

### Accessibility Rules

- Target WCAG AA contrast.
- All form controls must have labels.
- Focus states must be visible.
- Interfaces must be keyboard-accessible.
- Do not communicate status using color alone.

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py test
python manage.py runserver
```

Open `http://127.0.0.1:8000/` and sign in.

## Deployment

The project is configured for Docker-based deployment with PostgreSQL, Gunicorn, Nginx, and GitHub Actions.

See `DEPLOYMENT.md` for VPS setup, environment variables, Nginx, and GitHub Actions secrets.

## Make Commands

- `make install`
- `make migrate`
- `make seed`
- `make superuser`
- `make test`
- `make run`
