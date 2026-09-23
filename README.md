# NuviaMy

NuviaMy is a Django-based therapy practice management SaaS for solo therapists, psychologists, and multi-provider clinics. The project is built as a realistic portfolio application focused on secure client management, scheduling, clinical workflows, billing visibility, and a basic client portal.

## Product Vision

NuviaMy helps mental health professionals manage their practice from one calm, secure workspace:

- Manage solo practices and multi-therapist clinics.
- Track clients, appointments, sessions, notes, invoices, and payments.
- Provide clients with a simple portal for sessions, billing status, and insurance-related information.
- Model HIPAA-aware architecture and security practices for a realistic healthcare SaaS portfolio project.

This project is educational and portfolio-focused. It is designed with HIPAA-aware principles, but it is not certified for real clinical use.

## Implemented Product Areas

The current version includes these working modules:

- `accounts`: signup/onboarding, login/logout, role/profile model, practice ownership setup.
- `practices`: practice and therapist profile models with tenant scoping.
- `clients`: patient directory, create/edit/delete popups, practice-scoped client records, add note from client, assign package from client.
- `appointments`: calendar view, Monday-start calendar, create/edit/delete popups, today highlighting, tenant-scoped appointment scheduling.
- `clinical`: clinical notes list, create/edit/delete popups, optional appointment link, lock note behavior with `locked_at`.
- `billing`: invoices, package invoices, automatic invoice numbering, prepaid service packages, package usage tracking, package expiration/use rules.
- `documents`: client document upload/list/download/delete, file metadata, tenant-scoped downloads, local storage with R2-ready abstraction.
- `dashboard`: operational practice dashboard with today appointments, tasks, billing summary, recent invoices, and quick actions.
- `settings`: session package template configuration for reusable prepaid packages.
- `admin`: Django admin registration for core domain models.

The following apps exist at the model/admin level or are reserved for later phases:

- `portal`: client-facing access model exists, but client portal UI is not implemented yet.
- `audit`: audit model exists, but full event coverage is not implemented yet.
- `telehealth`: telehealth room model exists, but provider integration is not implemented yet.
- `notifications`: notification model exists, but delivery workers/providers are not implemented yet.

## Current Workflow Summary

### Dashboard

- Top action bar with quick create actions and profile menu.
- Practice metrics: monthly revenue, active patients, today's sessions, pending tasks.
- Today appointments panel.
- Tasks panel from notes, invoices, and notifications.
- Recent billing activity.

### Clients

- `My patients` grid with four desktop columns, two tablet columns, one mobile column.
- Create/edit/delete client using popups.
- Add clinical note directly from a client card.
- Assign a prepaid session package directly from a client card.
- Client cards are practice-scoped.

### Appointments

- Calendar page with Monday-first weeks.
- Current day highlighted.
- Day-level `+` opens appointment creation popup and pre-fills date/time.
- Existing appointment opens edit popup.
- Delete appointment from edit popup.
- Fallback create/edit pages remain available.

### Clinical Notes

- Notes workspace with list and popups.
- Notes link to client, therapist, and optional appointment.
- `Lock note` marks a note as final and sets `locked_at`.
- Locked notes are currently still editable; stricter edit rules can be added later.

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
- No-show/cancellation consumption rules are not finalized yet.

### Documents

- Upload client documents from `/documents/`.
- Documents are scoped to practice and client.
- Metadata stored in DB: original filename, content type, file size, portal visibility flag.
- Downloads go through Django authorization checks.
- Local `MEDIA_ROOT` storage works now.
- Cloudflare R2 support is configured through env vars but must be enabled in production.

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

## Next Recommended Work

The next major product step is a read-only client portal:

- Client login/access flow.
- Client dashboard showing upcoming appointments.
- Client-visible documents where `visible_to_client=True`.
- Client invoices and package balances.
- Available package templates for future purchase/request flow.
- Tenant isolation tests ensuring one client cannot access another client's data.

Other follow-up work:

- Define no-show/cancellation rules for package usage.
- Add document upload to client portal.
- Add payment provider integration.
- Add audit events for document, note, billing, and login actions.
- Add notification delivery providers.
- Move document storage fully to R2 in production and rotate exposed credentials.

## Security And Compliance Direction

NuviaMy should be built with healthcare-grade habits from the beginning:

- Every sensitive object belongs to a `Practice`.
- Users must only access data from their own practice.
- Clinical notes should never be written to logs.
- HTTPS is required in production.
- Secrets must live in environment variables, never in Git.
- Production services that handle PHI should support a Business Associate Agreement (BAA).
- Audit logging should be added before treating the project as production-like.

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
