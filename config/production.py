"""Fail before serving requests when production configuration is unsafe."""

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured


def validate_production_settings(config):
    errors = []
    if config['DEBUG']:
        errors.append('DJANGO_DEBUG must be false')

    secret = config['SECRET_KEY']
    if (len(secret) < 50 or len(set(secret)) < 5
            or secret.lower().startswith(('django-insecure-', 'dev-only-', 'change-me', 'replace_'))):
        errors.append('DJANGO_SECRET_KEY must be a strong, non-placeholder secret')

    hosts = config['ALLOWED_HOSTS']
    if not hosts or '*' in hosts:
        errors.append('DJANGO_ALLOWED_HOSTS must explicitly list allowed hosts')
    origins = config['CSRF_TRUSTED_ORIGINS']
    if not origins or any(not origin.startswith('https://') for origin in origins):
        errors.append('DJANGO_CSRF_TRUSTED_ORIGINS must contain HTTPS origins')

    for name in ('SECURE_SSL_REDIRECT', 'SESSION_COOKIE_SECURE', 'CSRF_COOKIE_SECURE'):
        if not config[name]:
            errors.append(f'{name} must be true')
    if config['SECURE_HSTS_SECONDS'] <= 0:
        errors.append('SECURE_HSTS_SECONDS must be positive')

    database = config['DATABASES']['default']
    if database['ENGINE'] != 'django.db.backends.postgresql':
        errors.append('Production requires PostgreSQL')
    elif not all(database.get(name) for name in ('NAME', 'USER', 'HOST', 'PASSWORD')):
        errors.append('PostgreSQL connection settings must be complete')
    elif (database['PASSWORD'] in {'dashboard_password', 'password', 'postgres'}
          or database['PASSWORD'].lower().startswith(('change-me', 'replace_'))):
        errors.append('POSTGRES_PASSWORD must not be a placeholder')

    # Even without an active Google connection, existing encrypted tokens may
    # need this key. Never generate or replace it automatically at startup.
    try:
        Fernet(config['FIELD_ENCRYPTION_KEY'].encode())
    except (ValueError, TypeError):
        errors.append('FIELD_ENCRYPTION_KEY must be a valid Fernet key')

    if errors:
        # Only setting names and requirements are reported, never secret values.
        raise ImproperlyConfigured('Unsafe production configuration: ' + '; '.join(errors))
