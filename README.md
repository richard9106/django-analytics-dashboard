# NuviaMy

NuviaMy is a Django-based practice management SaaS for solo therapists and multi-provider clinics. It brings clients, appointments, clinical documentation, billing, client forms and requests into one practice-scoped workspace. The intended clinical market is the United States.

## Current status

Last documentation review: **October 13, 2026**. The latest functional release includes initial consultations, client-specific appointment selection in notes, session documentation warnings, explicit note signatures, navigation improvements and cardless access.

- Production uses Docker Compose, PostgreSQL, Gunicorn and host Nginx at `nuviamy.com`.
- Stripe is currently in **test mode**. Published pricing is **USD 39 per active internal user/month** or **USD 421/user/year**.
- New practices receive **15 days without a card**. Paid billing starts only after an explicit checkout confirmation.
- Sign-in currently uses credentials only (`DJANGO_MFA_REQUIRED=false`). TOTP MFA and recovery controls remain available for later activation.
- Authenticated sessions expire after **one hour of inactivity** and have an **eight-hour absolute limit**.
- The latest functional release passed **527 PostgreSQL tests**, JavaScript interaction checks, migration/deployment checks and database role/backup-restore checks in CI. Production verification confirmed the initial consultation defaults, migrations and enabled clinical immutability guards.

The clinical-use goal remains open: this implementation is **not yet approved for real patient data**. Contracts, operating policies, clinical validation and independent security review still require evidence. A deployed feature or passing CI does not establish clinical readiness. See [Clinical readiness for the US](docs/clinical-readiness-us.md).

## Main client workflow

1. Create the client and assign a therapist when appropriate.
2. Use **Initial consultation → Schedule consultation** in the client record to arrange the brief introduction.
3. Schedule ongoing sessions in **Appointments**, using Calendar or List.
4. Create a session-linked note, review its content and have the responsible therapist sign it.
5. Manage treatment plans, invoices, documents, client forms and follow-up requests as needed.

Email delivery and online client payments are optional connections. Client creation and scheduling work without Gmail or Stripe Connect.

### Initial consultation versus client forms

These are separate workflows:

| Feature | Purpose | Where it lives |
| --- | --- | --- |
| Initial consultation | A brief introduction carried out by the therapist; 15 minutes suggested, editable to 10 minutes or another duration | Appointments, client overview, and Requests when explicitly requested |
| Client forms | Question templates assigned to the client, submitted through their portal and reviewed by staff | **Client forms** in the sidebar; existing `/intake/` routes are retained |
| Intake Note | A clinical note type | Clinical notes; its name is unchanged |

Initial consultation is a **session purpose**, separate from **format** (in person, video or phone). Calendar, Agenda and List identify it; short Day/Week events use compact cards. Manual duration survives start-time changes. Existing appointments remain Standard session.

The client overview shows Not scheduled, Scheduled, Completed or the latest cancellation/no-show state. Completion is an explicit session status; cancellation is not completion. This is a visible onboarding step, without a hard block on scheduling other sessions or retrospective classification of older records.

See [Initial consultations](docs/initial-consultation.md).

## Workspace behavior

### Overview

- Conditional first steps appear at the top, only while permitted setup actions remain incomplete.
- KPI cards summarize today's sessions, pending tasks, active clients and monthly revenue.
- Charts come before Billing at a glance; appointments and tasks follow at the bottom.
- Revenue line/area, session columns, session-status donut and invoice-status bars use practice-scoped data, numerical summaries and truthful empty states.
- Tasks and appointments have independent bounded scroll regions. Assigned tasks open their records; automatic alerts link to the relevant permitted workspace.
- Unpaid balances account for partial payments; draft and void invoices are excluded from outstanding balances.
- The compact orange free-access notice is shared across workspace action bars, with **Get subscription** linking to the per-user checkout flow.

### Clients

- Compact directory with search, therapist/contact/insurance/status columns and trailing actions.
- Client Workspace has Overview, Clinical, Billing and Documents tabs, according to permissions.
- Overview includes initial consultation progress, upcoming sessions, session history, client information and portal access.
- Clinical groups diagnoses, treatment plans and notes. Diagnosis create/edit dialogs keep the client fixed; treatment plans reuse that client's diagnosis records instead of copying them.
- Optional client photos, profile editing, appointment scheduling links, packages and document workflows remain practice-scoped.

### Appointments

- Primary **Calendar / List** switch. Calendar retains Monday-first Day, Week, Month and Agenda views.
- Therapists see their assigned sessions; owners/admins see sessions across their practice. The same scope applies to direct appointment URLs, note forms and related session summaries.
- Calendar supports search and therapist/status/format/sync filters, date navigation, create/edit dialogs, rescheduling, single-session cancellation and weekly recurrence.
- List is paginated at 25 sessions and preserves search, filters and page context. Documentation filters include All, Needs attention and Signed.
- **List and Agenda highlight past sessions without a signed note in orange**, using the scheduled end time regardless of appointment status. Text distinguishes Note missing from Signature pending; future and signed sessions are unflagged.
- **Create note** and **Session details** open dialogs from List. Note creation loads on demand, fixes client/therapist/session, retains validation errors and proceeds to review after saving. Full-page links remain available without JavaScript.
- Calendar availability supports date/range overrides, all-day or partial unavailability, repeated overrides, and review/edit/remove of individual changes. Weekly working hours remain the baseline fallback.
- Google Calendar sync metadata and Gmail reminder delivery are supported. Session purpose appears in exports and Google event descriptions.

See [Session documentation and signatures](docs/session-list-and-signatures.md).

### Clinical notes and signatures

- Notes link to client, therapist and an optional appointment/treatment plan, with optional treatment progress.
- Selecting a client loads **only that client's permitted appointments**. Changing clients clears the old appointment; valid existing selections survive editing and validation. Server-side choices reject appointments belonging to another client or outside the user's session scope.
- Review displays the client name prominently, labeled session/therapist metadata, readable note content and a separate signature section.
- Only the responsible therapist with clinical edit permission can sign. Signing requires confirmation, nonempty content, an ended session when linked, and a current review digest.
- Signing locks the note and creates a separate signature record containing signer identity, name snapshot, timestamp and content/association digest.
- **Lock without signing** is distinct from a signature. Existing locked notes remain unsigned until explicitly reviewed and signed; no historical signatures are invented.
- Finalized notes and signature records have application and PostgreSQL protection against updates, deletion and truncation. Signature metadata is included in clinical exports.
- Corrections require separate documentation; a dedicated addendum editor is still pending.
- Treatment plans support goals, interventions, diagnoses, treatment progress, review dates and review completion.

### Requests and client forms

- Requests is one compact inbox for public bookings and registered-client requests, with source filters and trailing three-dot actions.
- Public bookings retain approval/create-appointment and decline actions. Available slots follow practice availability and existing bookings.
- Registered requests retain review/resolve actions. **Initial consultation request** provides Schedule consultation with the client and session purpose preselected; resolving the request remains explicit.
- Client forms has a paginated assignment queue, search/status filters, review totals, form templates, question previews and permission-aware editing.
- Clients complete assigned forms in the portal; staff review numbered responses and record review status.
- Assigned questions are snapshotted. Editing a template affects future assignments, while existing assignments and responses retain their original content.

### Billing, subscriptions and access

- Invoices, partial/manual payments, balances, printable invoices/superbills, prepaid packages and package usage are implemented.
- Insurance payer/rate configuration is available; claims submission, eligibility, ERA/EOB and denial management are separate pending scope.
- Stripe Connect is optional for receiving client invoice payments. Signed webhooks record paid invoices; creating an invoice does not collect a payment.
- SaaS pricing is one plan per active internal user. Active owners, admins and therapists count; client portal users and inactive staff do not.
- Signup starts the fixed **15-day cardless period**, without creating a Stripe subscription. Cancelling checkout does not extend that deadline.
- Expiry preserves authorized record reading and exports while restricting writes. Paid conversion requires explicit checkout confirmation and starts billing immediately, with no additional Stripe trial.
- Before subscription Checkout, managers provide US professional billing details and an audited purchase declaration. Checkout also offers business tax ID collection. These declarations do not establish tax exemption; final Stripe address reconciliation remains a live-release requirement.
- Get subscription uses the current internal-user quantity. Monthly/annual checkout, period-change proration previews, subscription state, invoice history and Stripe Customer Portal are supported.
- Team changes attempt quantity synchronization. Periodic drift reconciliation remains pending.
- **Ten private early-access invitations** each cover one internal user in a new practice for twelve calendar months. They are email-bound, one-use links with a 30-day redemption expiry, not an automatic first-ten-signups promotion. Additional internal staff require voluntary paid conversion.

Private invitation command:

```bash
python manage.py issue_early_access_invitation SLOT EMAIL
```

`SLOT` is 1–10. The command prints a private link and sends no email. Deployment does not issue invitations automatically. See [Cardless trial and early access](docs/cardless-trial-early-access.md).

### Documents, portal and integrations

- Authorized client document upload, download, portal visibility and optional Google Drive export; local filesystem and Cloudflare R2 storage backends.
- Portal accounts are restricted to client-facing routes; temporary passwords must be changed. Clients can view their sessions/documents, submit requests/forms, message the practice and pay eligible invoices.
- Google OAuth supports Gmail, Calendar and Drive; tokens are encrypted through `FIELD_ENCRYPTION_KEY`. NuviaMy remains the source of truth.
- Optional client/team photos, team invitations and granular therapist permissions are implemented.
- Telehealth rooms are reserved for future provider integration; video appointment format is not an embedded telehealth service.

### Navigation, mobile and public pages

- Consistent SVG sidebar icons, permission-aware menus, compact tables and native dialogs.
- Shared breadcrumbs use routes and validated origin context. Moving from Appointments List/Agenda into note review and draft editing retains that origin and its filters; visiting the notes list keeps that step. Direct entry from Notes retains its own hierarchy.
- Mobile navigation collapses into a top menu; forms/dialogs stack, period navigation stays on one row, and Messages becomes a floating circular button.
- Pricing presents the single per-user plan centrally; mobile signup actions remain visible.
- Public footer links to support, privacy, cookie policy and Cookie settings. The cookie choice controls optional tour storage; essential authentication/CSRF cookies remain functional. No advertising analytics are installed.
- Help Center and support contact form are available. Versioned professional-preview terms, privacy and operator legal notice are published in the footer. Signup requires explicit terms acceptance, recorded in append-only audit with the actor, timestamp and notice versions. The preview permits fictional records only; paid-launch documents, provider contracts and clinical readiness evidence remain pending.

### Technical protections and operations

- Practice scoping, role/permission checks, protected audit evidence, denied-access/read events, encrypted OAuth tokens and environment-only secrets.
- Separate PostgreSQL runtime and migration roles; runtime cannot alter schema or mutate protected audit evidence.
- Configurable TOTP MFA, recovery codes, shared rate limits, session revocation/expiry and sensitive-action reauthentication. Current credentials-only sign-in is a development setting, not completion of clinical readiness.
- Owner/admin practice exports include tenant-scoped JSON records, available files and signature metadata. Export actions are audited.
- Staff monitoring covers integrations and aggregate operational state. Sentry is optional, with default PII/local-variable capture disabled.
- Backup tooling supports encrypted PostgreSQL backups to R2 and restore verification. CI validates isolated role separation and backup/restore; complete production recovery evidence remains a launch gate.

## Remaining work to review next

This is a checkpoint, not a new audit or a claim that every historical finding remains open.

### Product and usability

- Walk through the complete solo/team journey with representative test users: client → consultation → ongoing session → note/signature → invoice → follow-up.
- Therapist-specific availability; current availability is practice-wide.
- Dedicated addendum/correction workflow for finalized notes and patient-focused record/export requests.
- Periodic Stripe user-quantity reconciliation and visible failure/drift handling.
- Broader insurance workflows and telehealth-provider integration, if included in the launch scope.

### Paid launch and clinical readiness

- Complete paid-launch terms/taxes, retention and provider agreements; preview notices and versioned signup acceptance are implemented. SMTP, support forwarding and password reset have been verified with the operator.
- Complete a separately approved Stripe live-mode rollout and validate the payment/subscription lifecycle.
- Confirm launch states, provider contracts/BAAs, risk assessment, retention/legal-hold policy, incident response, patient rights workflows and production recovery evidence.
- Complete clinical workflow validation and independent security review before using real patient data.

Older audits and status documents describe their review date. Recheck their findings against current code and operational evidence rather than treating every old gap as still open. The October 9 pricing/card-collection observations, for example, predate the current cardless workflow.

## Documentation map

- [Deployment and operations](DEPLOYMENT.md)
- [Architecture](docs/architecture.md)
- [Initial consultations and client forms](docs/initial-consultation.md)
- [Session list and signatures](docs/session-list-and-signatures.md)
- [Cardless trial and private invitations](docs/cardless-trial-early-access.md)
- [Cookie choices and public footer](docs/cookie-choices-2026-10-09.md)
- [Professional-preview legal notices](docs/preview-legal-notices.md)
- [US professional billing preparation and draft commercial conditions](docs/business-billing-launch.md)
- [Client workspace review](docs/client-chart-ui-review.md)
- [Mobile UI review](docs/mobile-ui-review.md)
- [Clinical readiness assessment and release criteria](docs/clinical-readiness-us.md)
- [Historical product status](docs/product-status.md)
- [Stripe validation snapshot](docs/subscription-validation-2026-10-09.md)

## Development and release workflow

The application uses Django 5.2, PostgreSQL, server-rendered templates, native JavaScript and SVG charts. Keep the architecture lightweight for the VPS. UX decisions should be reviewed with the specialized NuviaMy UX agent, including typography, context, dialog behavior, validation and mobile layouts.

Local setup:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Configure a local database and development settings in .env.
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py runserver
```

Use a disposable PostgreSQL database for the suite that checks database roles, concurrency and immutability. Build the static manifest before running template tests:

```bash
python manage.py collectstatic --noinput
python manage.py test --noinput
node ops/check_cookie_choices.cjs
node ops/check_diagnosis_picker.cjs
node ops/check_appointments_calendar.cjs
node ops/check_client_session_picker.cjs
node ops/check_session_duration.cjs
```

Release process:

1. Work on a `codex/` branch; run relevant local checks and review the final diff.
2. Push and open a pull request. CI checks deployment settings, migrations, dependencies, static assets, interaction behavior, PostgreSQL tests, role separation and backup/restore.
3. Merge only the exact pull-request head whose required checks passed.
4. Main runs validation before the automatic VPS deployment of the tested commit.
5. Verify health, migrations, assets and relevant behavior in production using read-only checks.

See [DEPLOYMENT.md](DEPLOYMENT.md) for provisioning, roles, secrets, backups and rollback. Keep `.env`, credentials and uploaded files out of Git.

### Payment and storage configuration

SaaS invoices use the configured `STRIPE_INVOICE_TEMPLATE_ID`, assigned before Checkout to new and existing subscription customers. This is separate from patient invoices through Stripe Connect.

Current per-user Stripe settings:

```env
STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_PER_USER_MONTHLY=
STRIPE_PRICE_PER_USER_YEARLY=
```

Legacy solo/group/clinic price variables remain compatibility fallbacks in the code; they are not separate public product tiers. SaaS subscription checkout and practice Stripe Connect invoice payments are distinct flows.

Required webhook events:

```text
checkout.session.completed
checkout.session.async_payment_succeeded
customer.subscription.updated
customer.subscription.deleted
invoice.payment_failed
```

Storage uses local `MEDIA_ROOT` by default. For R2, configure `DJANGO_STORAGE_BACKEND=r2` and the `AWS_*` variables documented in `.env.example` and `DEPLOYMENT.md`. Production currently uses R2; backend support alone does not establish the required vendor/clinical operating evidence.

## Design system

The visual language uses Iris primary, Aqua supportive accents, Coral attention accents and Slate text/backgrounds; Manrope UI text with Lora editorial accents.

Prefer compact operational rows, clear client identity, labeled metadata, bounded lists, full-width workspaces and native dialogs. Use readable clinical text, visible focus, keyboard controls, mobile touch targets and text labels alongside status colors. Preserve current protections while improving usability.
