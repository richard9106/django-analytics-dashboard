# NuviaMy

NuviaMy is a Django-based therapy practice management SaaS for solo therapists, psychologists, and multi-provider clinics. The project is built as a realistic portfolio application focused on secure client management, scheduling, clinical workflows, billing visibility, and a basic client portal.

## Product Vision

NuviaMy helps mental health professionals manage their practice from one calm, secure workspace:

- Manage solo practices and multi-therapist clinics.
- Track clients, appointments, sessions, notes, invoices, and payments.
- Provide clients with a simple portal for sessions, billing status, and insurance-related information.
- Model HIPAA-aware architecture and security practices for a realistic healthcare SaaS portfolio project.

This project is educational and portfolio-focused. It is designed with HIPAA-aware principles, but it is not certified for real clinical use.

## Planned Core Domains

- `accounts`: users, roles, authentication, and permissions.
- `practices`: solo practices, clinics, therapists, and practice settings.
- `clients`: client records, contact details, status, emergency contacts, and insurance metadata.
- `appointments`: appointments, session status, calendar sync metadata, cancellations, and no-shows.
- `clinical`: session notes, progress notes, and clinical documentation workflows.
- `billing`: invoices, payments, balances, and future payment provider integration.
- `portal`: client-facing dashboard for sessions, billing, and requested information.
- `telehealth`: video session links and telehealth provider metadata.
- `dashboard`: therapist and practice overview screens.

## MVP Scope

The first implementation phase focuses on the foundation:

- Practice model that supports both solo providers and clinics.
- Therapist profile linked to Django users.
- Client records scoped to a practice.
- Appointment scheduling.
- Session notes.
- Protected therapist dashboard.
- Basic client portal.
- Tests for authentication and practice-level data isolation.
- Production domain target: `nuviamy.com`.

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
