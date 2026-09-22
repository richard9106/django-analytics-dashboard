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
