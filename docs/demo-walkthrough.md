# Demo Walkthrough

Prepare the project:

```bash
python -m venv .venv
source .venv/bin/activate
make install
make migrate
make seed
make superuser
make run
```

Open:

```text
http://127.0.0.1:8000/
```

Demo talking points:

- Dashboard is protected by Django auth.
- Metric cards are generated from ORM aggregations.
- Revenue by segment is rendered server-side into Chart.js data.
- Recent sales and events are real database records.
- Admin panel can manage all records at `http://127.0.0.1:8000/admin/`.

Suggested screenshot checklist:

- Login screen.
- Dashboard top metrics.
- Revenue chart.
- Admin list for Sales or Products.
