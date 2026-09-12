# Django Analytics Dashboard

Lightweight server-rendered Django dashboard for sales, customers, and operational events.

## Highlights

- Classic Django architecture with templates, views, models, and admin.
- Auth-protected dashboard for portfolio-style business analytics.
- Chart.js loaded from CDN, no frontend build pipeline required.
- SQLite by default for low resource usage.
- Seed command for demo data.
- Tests for protected dashboard access and key metrics.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo_data
python manage.py test
python manage.py runserver
```

Open `http://127.0.0.1:8000/` and sign in.

## Portfolio Notes

This project demonstrates Django's strengths for internal tools: admin, ORM aggregation, protected views, templates, reusable metrics, and simple operational dashboards without heavy infrastructure.

## Documentation

- Architecture: `docs/architecture.md`
- Demo walkthrough: `docs/demo-walkthrough.md`

## Make Commands

- `make install`
- `make migrate`
- `make seed`
- `make superuser`
- `make test`
- `make run`
