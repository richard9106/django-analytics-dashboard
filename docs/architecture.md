# Architecture

This project is a traditional Django internal dashboard. It intentionally avoids a separate frontend build so it can run cheaply and be reviewed quickly.

## Boundaries

- `config/`: Django settings, URL routing, and WSGI entrypoint.
- `apps/dashboard/models.py`: Customers, products, sales, and operational events.
- `apps/dashboard/views.py`: Auth-protected dashboard view and ORM aggregations.
- `templates/dashboard/index.html`: Server-rendered UI with a small Chart.js chart.
- `static/dashboard.css`: Responsive CSS without a build step.
- `apps/dashboard/management/commands/seed_demo_data.py`: Repeatable demo data command.

## Data Flow

1. Admin or seed command creates customers, products, sales, and events.
2. `DashboardView` aggregates totals with Django ORM queries.
3. The template renders metric cards, a revenue chart, recent events, and recent sales.
4. Access is protected with Django's built-in auth using `LoginRequiredMixin`.

## Resource Usage

- One Django process.
- SQLite by default.
- Chart.js via CDN.
- No Celery, Redis, Node, Webpack, or background workers.

## Portfolio Value

This demonstrates the kind of practical Django work common in internal business tools: admin models, secure views, ORM aggregation, server-rendered UX, and simple deployability.
