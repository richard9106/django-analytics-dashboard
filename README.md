# NuviaMy

NuviaMy is a Django-based therapy practice management SaaS for solo therapists, psychologists, and multi-provider clinics. The project targets clinical use in the United States and focuses on secure client management, scheduling, clinical workflows, billing, subscriptions, document storage, Google integrations, and a client portal.

## Product Vision

NuviaMy helps mental health professionals manage their practice from one calm, secure workspace:

- Manage solo practices and multi-therapist clinics.
- Track clients, appointments, sessions, notes, treatment plans, invoices, subscriptions, documents, and client requests.
- Provide clients with a portal for appointments, documents, intake, and practice communication.
- Implement and validate the technical and operational controls required for a clinical healthcare SaaS.

Production uses separate runtime and migration PostgreSQL credentials; the runtime cannot change schema or mutate audit evidence. See `DEPLOYMENT.md` for provisioning and release verification.

During pre-client development, sign-in uses credentials only (`DJANGO_MFA_REQUIRED=false`). MFA is preserved for later activation and remains a clinical readiness requirement to validate before onboarding.

The product goal is real clinical use in the United States with demonstrable HIPAA compliance. The current implementation is not yet approved for real patient data: technical controls, contracts, operating policies, and independent validation remain to be completed. HHS does not certify software as HIPAA compliant. See `docs/clinical-readiness-us.md` for the readiness assessment and release criteria.

## Implemented Product Areas

The current version includes these working modules:

- `accounts`: signup, email-based login/logout, mandatory staff TOTP MFA, single-use recovery codes, account-wide session revocation, idle/absolute session limits, sensitive-action reauthentication, password recovery, editable profiles with optional photos, role/profile model, practice ownership setup, client password-change enforcement, team management, temporary/custom-password invitations, Gmail/SMTP delivery, granular therapist permissions, and active-user billing quantity sync.
- `practices`: practice and therapist profile models, tenant scoping, integration settings, encrypted Google OAuth tokens, and Stripe Connect payout onboarding.
- `clients`: Odoo-style tree directory, optional client photos, tenant-scoped client records, full Client Workspace, breadcrumbs, create/edit/delete popups, add note from client, assign package from client, and create appointment popup from client workspace.
- `appointments`: Monday-start Day/Week/Month calendar, client search, therapist/status/type/sync filters, create/edit/delete popups, today highlighting, tenant-scoped scheduling, weekly recurrence, date-based availability from the calendar, weekly baseline availability, visible unavailable blocks, Google Calendar sync, and Gmail reminder command.
- `clinical`: clinical notes, diagnosis records, treatment plans, linked treatment progress, lock note behavior, review-due workflow.
- `billing`: invoices, package invoices, superbills, automatic invoice numbering, prepaid service packages, package usage tracking, insurance payer/rate settings, per-active-user Stripe subscription checkout, billing-period changes with proration previews, SaaS invoice history, Stripe Customer Portal, Stripe Connect client payouts, 15-day trial, webhooks, and practice subscription persistence.
- `documents`: client document upload/list/download/delete, file metadata, tenant-scoped downloads, Google Drive export, local storage with Cloudflare R2 production support.
- `portal`: client-facing dashboard, portal access accounts, enforced temporary password change, secure client/practice conversations, visible documents, appointment change requests, intake packet completion, and Stripe Checkout invoice payments routed to the practice's connected account.
- `intake`: practice intake templates, client packet assignment, client portal submission workflow.
- `requests`: practice-side inbox for client portal requests and appointment change requests.
- `notifications`: appointment reminder model and Gmail-based reminder delivery command.
- `audit`: protected append-only events, actor snapshots, sensitive-module reads and access denials, alongside auth, documents, clinical, billing, portal, intake, and integration events. PostgreSQL guards protect audit events and finalized notes; privileged database administration and complete retention policies remain separate readiness work.
- `dashboard`: operational practice dashboard with today appointments, automatic alerts, assignable team tasks, billing summary, recent invoices, six-month revenue/session charts, quick actions, a clients-first setup guide, and a contextual guided onboarding tour.
- `settings`: session package templates, insurance settings, portal access, Google integrations, Google workspace, and legacy weekly availability baseline management.
- `telehealth`: telehealth room model reserved for future provider integration.
- `admin`: Django admin registration for core domain models, including subscriptions.

## Current Workflow Summary

### Dashboard

- Top action bar with quick create actions and profile menu.
- Practice metrics: monthly revenue, active patients, today's sessions, pending tasks.
- Today appointments panel.
- Tasks panel from notes, invoices, notifications, portal requests, and treatment plan reviews.
- Recent billing activity.
- First-steps setup panel: add a client, open calendar availability, schedule a session, and invite a team when needed.
- Client creation and scheduling work without Gmail or Stripe Connect. Connect these services when email delivery or online client payments are needed; payment-provider checks remain in payment flows.
- Six-month revenue trend and appointment volume charts.
- Contextual guided tour moves through Overview, Appointments, Clients, Notes, Billing, Documents, Intake, Requests, Settings, and setup.
- Tour completion is stored in browser local storage and hides the launch button.
- Permission-denied navigation is hidden when possible and direct unauthorized access returns a friendly warning/redirect instead of a raw 403 page.

### Clients

- `My patients` tree view with client, therapist, phone, insurance, status, and actions columns.
- Create/edit/delete client using popups.
- Client Workspace combines profile data, latest session, portal access, invoices, clinical notes, treatment plans, documents, and breadcrumbs back to the directory.
- Optional client photos appear in the directory and workspace.
- Client Directory uses a compact tree/table view with therapist, phone, insurance, status, and actions.
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
- Availability is managed from the calendar through the `Set availability` action.
- Date-specific availability can mark a day or date range as available, unavailable all day, or unavailable for a specific time range.
- Date-specific availability can repeat weekly or monthly for a configured number of occurrences.
- Clicking an unavailable calendar time prompts the user to enable that day/range before scheduling.
- Weekly availability remains as a baseline fallback; date-specific calendar availability overrides it.
- Unavailable time is visibly shaded in Day/Week calendar views.
- Week is the default calendar view; Year view was removed to keep calendar navigation focused.
- Search and compact filters preserve state while navigating the calendar.
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
- Staff can record partial or full manual payments using cash, check, ACH, insurance, card, or other methods, with balance tracking.
- Insurance settings support common payer templates and practice-specific reimbursement rates.
- Practice owners/admins can configure Stripe Connect from Profile Settings so client payments go to the practice.
- Clients can pay eligible sent/overdue invoices from the portal through Stripe Checkout.
- Signed Stripe webhooks mark client invoices as paid and record `paid_at`.
- Stripe Checkout creates SaaS subscriptions using per-active-user pricing.
- New signups are routed to Stripe Checkout with a 15-day free trial and card collection.
- Active owners, admins, and therapists count as billable users; client portal users and deactivated staff do not.
- Team create/deactivate/reactivate actions best-effort sync the Stripe subscription quantity.
- Stripe webhooks update local `PracticeSubscription` records for checkout completion, subscription updates/deletions, and failed payments.
- Profile Settings includes billing-period switching, Stripe proration previews, SaaS invoice history, and Stripe Customer Portal access.

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
- Clients can pay their own open invoices; tenant and client ownership are checked before Checkout is created.

### Google Integrations

- A single Google OAuth connection supports Gmail, Calendar, and Drive scopes.
- OAuth tokens are encrypted at rest using Fernet through `FIELD_ENCRYPTION_KEY`.
- Gmail is used for appointment reminder delivery when connected.
- Connected Gmail can send team-member invitations with temporary passwords.
- Google Calendar sync mirrors appointment records to Google.
- Google Drive export uploads authorized client documents.
- NuviaMy remains the source of truth; Google is treated as an external mirror/export target.

### Permissions And Team

- Owners/admins can configure therapist Read/Create/Edit/Delete access for each major workspace area, including Tasks.
- Unauthorized navigation is hidden where possible; direct unauthorized URLs redirect with a friendly warning instead of showing a raw 403 page.
- Optional photos are supported for clients and internal team members and use the configured media/R2 storage backend.

### Team And Permissions

- Team members can be therapists or practice admins.
- Owners/admins can set therapist Read/Create/Edit/Delete permissions for Clients, Appointments, Clinical, Billing, Documents, Intake, Requests, and Tasks.
- Team members can be activated, deactivated, invited again, assigned a custom password, or permanently deleted when safe.
- Optional team photos appear in Team Management.

### Help And Legal

- Low-cost Help Center with server-rendered FAQs and search at `/help/`.
- Support contact form delivered through configured email.
- Cookie Policy at `/cookie-policy/`.
- Current cookies are limited to session, CSRF, and guided-tour local storage; no advertising analytics are installed.

### Data Export And Monitoring

- Owner/admin-only practice data export at Profile Settings.
- Exports are ZIP archives containing tenant-scoped JSON records and available document files.
- Export requests are recorded in the audit log.
- Staff-only operational monitoring page: `/staff/monitoring/`.
- Monitoring checks database, email, Stripe, Google OAuth, R2, aggregate metrics, and failed notifications.
- Sentry integration is conditional on `SENTRY_DSN` and does not send default PII.
- PostgreSQL backups run daily, are retained locally, encrypted with GPG, copied to R2, and periodically restore-verified.

### Stripe Subscriptions

- Public pricing page uses one per-active-user plan.
- Monthly and yearly Stripe Price IDs are configured through environment variables.
- Signup preserves selected plan/period and redirects to Checkout after account creation.
- Checkout uses a 15-day trial with card collection.
- Checkout success routes users to the dashboard guided tour.
- Webhook endpoint: `/billing/stripe/webhook/`.
- Stripe Connect onboarding is separate from the NuviaMy SaaS subscription and is used for practice client-payment payouts.
- Client invoice Checkout uses destination transfers to the practice's connected Stripe account; NuviaMy does not receive those funds as the final payee.

Required webhook events:

```text
checkout.session.completed
checkout.session.async_payment_succeeded
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
STRIPE_PRICE_PER_USER_MONTHLY=
STRIPE_PRICE_PER_USER_YEARLY=
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

## Remaining Product Roadmap

- Add Stripe subscription quantity reconciliation for failed/manual team changes.
- Improve calendar availability editing/deleting for existing overrides.
- Add filters/search polish for remaining dense clinical/admin tables where needed.
- Add Dropbox OAuth/export support.
- Complete production security, legal, HIPAA/BAA, retention, and incident-response review before clinical use.

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
