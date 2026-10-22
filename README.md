# NuviaMy Platform

Repository: [richard9106/nuviamy-platform](https://github.com/richard9106/nuviamy-platform). Local checkout: `nuviamy-platform`. The production server retains its existing internal directory and Docker Compose project identity so the repository rename does not change persistent services or data volumes.

NuviaMy is a Django-based practice management SaaS for solo therapists and multi-provider clinics. It brings clients, appointments, clinical documentation, billing, client forms and requests into one practice-scoped workspace. The intended clinical market is the United States.

## Current status

Last documentation review: **October 20, 2026**. The application is commercially deployed on AWS, live subscription billing is enabled, and Google OAuth verification remains pending according to the operator. Recent releases include signed immutable addenda, email two-step sign-in, native S3 storage, AWS recovery validation and GitHub OIDC/SSM deployment.

- Production at `nuviamy.com` runs on AWS EC2 in `us-east-1`, using Docker Compose, PostgreSQL, Gunicorn and host Nginx with HTTPS. Native S3 holds private documents and encrypted scheduled database backups in separate buckets. AWS is the sole active application origin; the former Contabo app and its timers are stopped.
- Stripe mode follows the protected deployment credentials; the operator has authorized **live subscription billing**. Published pricing (excluding applicable taxes) is **USD 39 per active internal user/month** or **USD 421/user/year**.
- New practices receive **30 days without a card**. Paid billing starts only after an explicit checkout confirmation.
- Email two-step sign-in is implemented and recorded as enabled in the October 20 operational evidence. It is independent of optional authenticator TOTP MFA (`DJANGO_MFA_REQUIRED=false` in the documented baseline). See [Email two-step sign-in](#email-two-step-sign-in).
- Authenticated sessions expire after **one hour of inactivity** and have an **eight-hour absolute limit**.
- Release CI runs the full PostgreSQL test suite, JavaScript interaction checks, migration/deployment checks and database role/backup-restore checks. Production verification confirmed the initial consultation defaults, migrations and enabled clinical immutability guards.

The AWS BAA is activated according to the operator; its four-page AWS Business Associate Addendum has also been reviewed locally. Account-specific acceptance is electronic through AWS Artifact; the PDF itself does not contain an account ID or acceptance timestamp. Keep the confidential agreement and acceptance evidence outside Git. This AWS agreement is distinct from the prepared customer BAA/DPA documents.

The standard customer agreements now cover ordinary real-client records during the trial and paid service, subject to the Processing Schedule’s scope and exclusions. This contractual change does not establish HIPAA certification or close outstanding operational evidence, provider/integration assessment and independent security review. See the [October 20 internal evidence audit](docs/compliance/internal-audit-2026-10-20.md) and the [clinical security dossier](docs/compliance/README.md). Historical pre-migration entries are superseded for hosting by dated AWS cutover evidence. Google OAuth verification is separate from these obligations.

## Standard practice agreements and onboarding

Signup collects the practice legal name and address, owner identity and representative title. One unchecked acceptance explicitly covers the Terms of Use, DPA, applicable BAA and Standard Processing Schedule, and acknowledges the Privacy Notice. The complete standard offer is public at `/accounts/agreements/`. It applies from acceptance through the 30-day trial and subsequent paid subscription; upgrading does not request another BAA signature or wait for manual contract preparation.

Exact document texts, consent, customer identity, timestamp and versions are retained in immutable, SHA-256-verified acceptance snapshots with PostgreSQL mutation/truncation guards and audit evidence. **Settings → Contracts** lets owners download their accepted documents and receipt. Existing owners must expressly accept there; no acceptance is backfilled. The dashboard prompt disappears after acceptance. Authentication must be recent for an existing owner to accept. Downloads and acceptance remain available after trial expiry.

Older custom requests, packets and signatures are preserved. Their historical terms are not silently replaced. The legacy custom workflow is available at `/accounts/contracts/?custom=1`; it is no longer the ordinary signup path. Clinical-data exclusions and external integration restrictions remain in the Standard Processing Schedule. See [the rollout and verification notes](docs/validation/standard-agreements-30-day-trial-2026-10-20.md).

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

- An Activities icon beside the account menu groups permitted setup actions and owner agreement acceptance into a compact dropdown. Its badge counts pending setup items and clears as they are completed; trial status remains in the toolbar.
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
- Signed notes support a dedicated reviewed and signed addendum workflow. Addenda preserve the original, record author/time/reason and a linked digest, are immutable, and are included in clinical exports. Only the responsible therapist with edit permission can sign them.
- Treatment plans support goals, interventions, diagnoses, treatment progress, review dates and review completion.

### Requests and client forms

- Requests is one compact inbox for public bookings and registered-client requests, with source filters and trailing three-dot actions.
- Public bookings retain approval/create-appointment and decline actions. Available slots follow practice availability and existing bookings.
- Registered requests retain review/resolve actions. **Initial consultation request** provides Schedule consultation with the client and session purpose preselected; resolving the request remains explicit.
- Client forms has a paginated assignment queue, search/status filters, review totals and a [page-based form builder](docs/intake-form-builder.md). Templates support short/long text, single/multiple choice, dropdown and yes/no answers, required questions, page titles/instructions, ordering and a client preview. Assigned forms retain their original snapshot; portal clients complete pages with Previous/Next controls.
- Clients complete assigned forms in the portal; staff review numbered responses and record review status.
- Assigned questions are snapshotted. Editing a template affects future assignments, while existing assignments and responses retain their original content.

### Billing, subscriptions and access

- Invoices, partial/manual payments, balances, printable invoices/superbills, prepaid packages and package usage are implemented.
- Insurance has a shared available catalogue and practice-local payer enable/disable controls. Existing configured catalogue rates are enabled by migration; the global catalogue is not modified. Custom payer removal deactivates it and preserves references.
- Clients can link an enabled payer, billing type, rate state and expected client share; legacy insurance text is retained without automatic name matching. Invoice forms explicitly load rate suggestions by payer/state/service, require a confirmed patient share and retain the accepted payer/rate snapshot. Catalogue changes do not recalculate saved invoices.
- Insurance invoices split the recorded charge between client and insurer. The client portal and Stripe Checkout collect only the remaining client share; manual insurance payments are allocated separately. Stripe client-share events are recorded idempotently and do not mark the insurer portion paid. Exports include payer configuration and saved allocation details.
- Electronic claims, credentialing/enrollment, eligibility, ERA/EOB import, contractual write-offs, secondary coverage and denial management remain separate pending scope. Rates and shares are practice-entered references, not verified coverage or guaranteed reimbursement. See [insurance workflow](docs/insurance-workflow.md).
- Stripe Connect is optional for receiving client invoice payments. Signed webhooks record paid invoices; creating an invoice does not collect a payment.
- SaaS pricing is one plan per active internal user. Active owners, admins and therapists count; client portal users and inactive staff do not.
- Signup starts the fixed **30-day cardless period**, without creating a Stripe subscription. Cancelling checkout does not extend that deadline.
- Expiry preserves authorized record reading and exports while restricting writes. Paid conversion requires explicit checkout confirmation and starts billing immediately, with no additional Stripe trial.
- Before subscription Checkout, managers provide international professional billing details and an audited purchase declaration. Checkout also offers business tax ID collection. These declarations do not establish tax exemption. No country-based activation block is applied; international tax treatment remains a live-release requirement.
- Get subscription uses the current internal-user quantity. Monthly/annual checkout, period-change proration previews, subscription state, invoice history and Stripe Customer Portal are supported.
- Team changes attempt quantity synchronization. Periodic drift reconciliation remains pending.
- **Ten private early-access invitations** each cover one internal user in a new practice for twelve calendar months. They are email-bound, one-use links with a 30-day redemption expiry, not an automatic first-ten-signups promotion. Additional internal staff require voluntary paid conversion.

Private invitation command:

```bash
python manage.py issue_early_access_invitation SLOT EMAIL
```

`SLOT` is 1–10. The command prints a private link and sends no email. Deployment does not issue invitations automatically. See [Cardless trial and early access](docs/cardless-trial-early-access.md).

### Documents, portal and integrations

- Authorized client document upload, download, portal visibility and optional Google Drive export; local filesystem, Cloudflare R2 and native AWS S3 storage backends. Production uses native S3 with instance-role credentials; R2 is a legacy backend.
- Portal accounts are restricted to client-facing routes and activated through emailed setup links; legacy temporary passwords still require a change. Clients can view their sessions/documents, submit requests/forms, message the practice and pay eligible invoices.
- Google OAuth supports Gmail, Calendar and Drive; tokens are encrypted through `FIELD_ENCRYPTION_KEY`. NuviaMy remains the source of truth.
- Optional client/team photos, team invitations and granular therapist permissions are implemented.
- Telehealth rooms are reserved for future provider integration; video appointment format is not an embedded telehealth service.

### Navigation, mobile and public pages

- Consistent SVG sidebar icons, permission-aware menus, compact tables and native dialogs.
- Mobile navigation collapses into a top menu; forms/dialogs stack, period navigation stays on one row, and Messages becomes a floating circular button.
- Pricing presents the single per-user plan centrally; mobile signup actions remain visible.
- Public marketing pages share canonical/social metadata, versioned assets and a fictional-data product tour. Product guides explain real workflows and current integration limits. Public GET/HEAD pages on `www.nuviamy.com` redirect to the canonical host; app routes and form POSTs are excluded. See `docs/validation/public-website-refresh-2026-10-22.md`.
- Public footer links to support, privacy, cookie policy and Cookie settings. The cookie choice controls optional tour storage; essential authentication/CSRF cookies remain functional. No advertising analytics are installed.
- Help Center and support contact form are available. Versioned service and commercial subscription conditions, privacy and operator legal notice are published in the footer. Subscription Checkout requires separate unchecked acceptance of the current commercial version, stored in audit and Checkout metadata. Signup requires explicit terms acceptance, recorded in append-only audit with the actor, timestamp and notice versions. The standard agreements cover ordinary real-client records during trial and paid use; special record categories and external clinical flows remain subject to the schedule. International tax decisions and outstanding provider/security evidence remain separate operational work.

### Profile settings

Personal details, subscription billing and optional connections are grouped in compact cards. Google connection status is independent of Gmail sending permission, with the connected account and selected services shown explicitly. Empty invoices and sensitive practice exports use expandable sections. See the [profile settings review](docs/profile-settings-review-2026-10-20.md) for validation and rollout scope.

### Technical protections and operations

- Practice scoping, role/permission checks, protected audit evidence, denied-access/read events, encrypted OAuth tokens and environment-only secrets.
- Separate PostgreSQL runtime and migration roles; runtime cannot alter schema or mutate protected audit evidence.
- Configurable TOTP MFA, recovery codes, shared rate limits, session revocation/expiry and sensitive-action reauthentication. Email two-step sign-in is separate from optional TOTP; available authentication controls do not by themselves establish clinical readiness.
- Owner/admin practice exports include tenant-scoped JSON records, available files and signature metadata. Export actions are audited.
- Staff monitoring covers integrations and aggregate operational state. Sentry is optional, with default PII/local-variable capture disabled.
- Production backup tooling uploads encrypted PostgreSQL backups to a separate private S3 bucket using the host role. The October 20 cutover records retrieval, authenticated decryption, an actual restore into a disposable database and comparison of all 52 SQL table counts. Private document hashes and protected note integrity were also checked. Versioned S3 documents and daily encrypted instance snapshots complement database backups; recovery objectives, alerts and key custody still need operational closure.

## Remaining work to review next

This is a checkpoint, not a new audit or a claim that every historical finding remains open.

### Product and usability

- Walk through the complete solo/team journey with representative test users: client → consultation → ongoing session → note/signature → invoice → follow-up.
- Therapist-specific availability; current availability is practice-wide.
- Validate the delivered signed-addendum workflow with a clinical reviewer; complete patient-focused record/export request procedures.
- Periodic Stripe user-quantity reconciliation and visible failure/drift handling.
- Broader insurance workflows and telehealth-provider integration, if included in the launch scope.

### Paid launch and clinical readiness

- Finalize international taxes and tax-inclusive/exclusive price presentation, retention and provider agreements; published commercial conditions and separate versioned Checkout acceptance are implemented. SMTP, support forwarding and password reset have been verified with the operator.
- Stripe live rollout is complete. Observe subsequent real payment/subscription delivery after the AWS migration; no new charge was created by the cutover checks. Complete Google OAuth verification in Google Console; identity scopes were reduced to `openid email`, with additional scopes selected by integration.
- Confirm launch states, provider contracts/BAAs, risk assessment, retention/legal-hold policy, incident response, patient rights workflows and remaining continuity controls. AWS migration and an actual database recovery are already documented.
- Complete clinical workflow validation and independent security review before using real patient data.

Older audits and status documents describe their review date. Recheck their findings against current code and operational evidence rather than treating every old gap as still open. The October 9 pricing/card-collection observations, for example, predate the current cardless workflow.

## Documentation map

- [AWS production cutover and successful deployment — October 20](docs/validation/aws-cutover-2026-10-20.md)
- [AWS foundation and infrastructure controls](docs/validation/aws-foundation-2026-10-20.md)
- [AWS isolated rehearsal and restore proof](docs/validation/aws-rehearsal-2026-10-20.md)
- [Stripe live activation](docs/live-billing-activation-2026-10-15.md)
- [Stripe live webhook delivery proof](docs/stripe-live-webhook-proof-2026-10-15.md)
- [Google OAuth scope minimization and deployment](docs/validation/google-oauth-scopes-2026-10-20.md)
- [Current internal audit and remaining evidence](docs/compliance/internal-audit-2026-10-20.md)
- [Prepared customer DPA, BAA and clinical schedule](docs/contracts/README.md)
- [Deployment and operations](DEPLOYMENT.md)
- [Architecture](docs/architecture.md)
- [Initial consultations and client forms](docs/initial-consultation.md)
- [Session list and signatures](docs/session-list-and-signatures.md)
- [Cardless trial and private invitations](docs/cardless-trial-early-access.md)
- [Cookie choices and public footer](docs/cookie-choices-2026-10-09.md)
- [Professional-preview legal notices](docs/preview-legal-notices.md)
- [International professional billing preparation and draft commercial conditions](docs/business-billing-launch.md)
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
4. Main runs validation before deploying the tested commit to AWS through GitHub OIDC and a restricted SSM document. No static AWS keys or inbound runner SSH are required. The legacy Contabo deployment is skipped.
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

Storage uses local `MEDIA_ROOT` by default. For R2, configure `DJANGO_STORAGE_BACKEND=r2` and the `AWS_*` variables documented in `.env.example` and `DEPLOYMENT.md`. Production uses `DJANGO_STORAGE_BACKEND=s3`, `AWS_S3_REGION_NAME=us-east-1` and the private documents bucket, with no static S3 credentials or custom endpoint so the instance role is used. `BACKUP_S3_BUCKET` selects the separate backups bucket. R2 settings remain for legacy compatibility, not the active production destination.

## Design system

The visual language uses Iris primary, Aqua supportive accents, Coral attention accents and Slate text/backgrounds; Manrope UI text with Lora editorial accents.

Prefer compact operational rows, clear client identity, labeled metadata, bounded lists, full-width workspaces and native dialogs. Use readable clinical text, visible focus, keyboard controls, mobile touch targets and text labels alongside status colors. Preserve current protections while improving usability.

New professional workspace registrations send an operator email after the account transaction commits. `SIGNUP_NOTIFICATION_EMAIL` defaults to `support@nuviamy.com` in Compose (set it empty to disable); notifications contain the registrant name, email, practice and registration date, never passwords or clinical data. SMTP failures are logged without blocking registration. Patient and team invitations do not trigger this signup alert.

Live billing rollout completed October 15: production uses the separately validated live prices, invoice template, API keys and endpoint signing secret. Sandbox subscription/customer/session references were archived and detached before activation; existing local trial/invitation entitlements were preserved. Commercial availability does not authorize identifiable clinical records.

## Clinical security baseline — October 15, 2026

Staff and client portal access use single-use account setup links (up to 48 hours).
Administrators do not choose, see or email a recipient's password. Resending a pending
invitation revokes the earlier link; recovery for an established account leaves its
password unchanged until the recipient completes the reset. Disabled accounts cannot
receive new links. Transactional SMTP sends neutral messages without client names
or clinical details. Pending active staff still count towards paid seats.

Sentry exports only exception types and structural stack locations; request data,
messages, locals, breadcrumbs and performance transactions are discarded. Google
Calendar synchronization sends neutral reserved-time blocks without client names,
notes, meeting links or locations. Previously exported events require separate review.
Client document uploads have a 10 MB limit and container/type validation; this is
not malware scanning and does not establish that every upload route is approved.

`ops/offsite_config_backup.py` captures an authenticated encrypted configuration/key
snapshot on the operator's computer, with the decryption key kept outside the VPS.
See [recovery evidence and instructions](docs/compliance/recovery.md). This snapshot
does not replace database backups or historical document recovery.

## Signed addenda and recovery preparation — October 16, 2026

Signed notes accept reviewed, signed addenda without changing the original. Addenda
are immutable, restricted to the responsible therapist and included in exports.
The [readiness progress report](docs/compliance/readiness-progress-2026-10-16.md) records
the access matrix, fictional workflow tests and document snapshot evidence.
See the [migration plan](docs/compliance/migration-plan.md) for isolated preparation
and cutover safeguards. No new provider or clinical release is activated by these tools.

### Email two-step sign-in

`DJANGO_EMAIL_TWO_STEP_REQUIRED=true` requires a one-use six-digit email code after
password authentication, including admin and client portal access. It uses the configured
transactional SMTP sender. Codes expire after 10 minutes, are stored only as keyed hashes,
are bound to the account and browser sign-in, and are invalidated after verification or
resend. Re-sends have a 60-second account cooldown; five incorrect codes lock verification
for 15 minutes, across browsers. Password challenges expire after 10 minutes.
The email step is independent of the optional authenticator/QR setting `DJANGO_MFA_REQUIRED`.
Existing sessions must complete verification when it is enabled; no bulk email is sent.
The login form asks for the password once, followed by the code. Changing the sign-in email
through the profile is disabled while email verification is mandatory; contact support for
an identity-checked change. SMTP failures never grant access. Maintain a protected operator
SSH recovery route and verify each active account has a deliverable email before activation.
Do not log codes, include them in URLs, or use this feature as a claim of HIPAA certification.
