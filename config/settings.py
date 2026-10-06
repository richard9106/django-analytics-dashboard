from pathlib import Path
import os

from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

from .production import validate_production_settings

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-only-secret-key')
DJANGO_ENVIRONMENT = os.getenv('DJANGO_ENVIRONMENT', '').strip().lower()
if DJANGO_ENVIRONMENT not in {'', 'development', 'test', 'production'}:
    raise ImproperlyConfigured('DJANGO_ENVIRONMENT must be development, test, or production')
DEBUG = os.getenv('DJANGO_DEBUG', 'false' if DJANGO_ENVIRONMENT == 'production' else 'true').lower() == 'true'
if not DJANGO_ENVIRONMENT:
    DJANGO_ENVIRONMENT = 'development' if DEBUG else 'production'
ALLOWED_HOSTS = [host.strip() for host in os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',') if host.strip()]

SENTRY_DSN = os.getenv('SENTRY_DSN', '')
SENTRY_ENVIRONMENT = os.getenv('SENTRY_ENVIRONMENT', 'development' if DEBUG else 'production')
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.05'))
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=SENTRY_ENVIRONMENT,
        integrations=[DjangoIntegration()],
        send_default_pii=False,
        include_local_variables=False,
        traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
    )

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # funtionalities
    'config.apps.SummernoteConfig',
    # core apps
    'apps.dashboard',
    'apps.practices',
    'apps.clients',
    'apps.appointments',
    'apps.clinical',
    'apps.accounts',
    'apps.billing',
    'apps.portal',
    'apps.documents',
    'apps.audit',
    'apps.telehealth',
    'apps.notifications',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'apps.accounts.security_middleware.SecuritySessionMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {'context_processors': [
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
            'apps.portal.context_processors.portal_request_badge',
            'apps.accounts.access.permission_context',
            'apps.accounts.context_processors.security_context',
        ]},
    },
]
WSGI_APPLICATION = 'config.wsgi.application'

if os.getenv('POSTGRES_DB'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('POSTGRES_DB'),
            'USER': os.getenv('POSTGRES_USER'),
            'PASSWORD': os.getenv('POSTGRES_PASSWORD'),
            'HOST': os.getenv('POSTGRES_HOST', 'localhost'),
            'PORT': os.getenv('POSTGRES_PORT', '5432'),
        }
    }
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media/')
DJANGO_STORAGE_BACKEND = os.getenv('DJANGO_STORAGE_BACKEND', '')
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

if DJANGO_STORAGE_BACKEND == 'r2':
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_ENDPOINT_URL = os.getenv('AWS_S3_ENDPOINT_URL')
    AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'auto')
    AWS_S3_SIGNATURE_VERSION = 's3v4'
    AWS_S3_ADDRESSING_STYLE = 'path'
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = True
    AWS_S3_FILE_OVERWRITE = False
    STORAGES['default'] = {'BACKEND': 'storages.backends.s3.S3Storage'}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
# Summernote attachments have no Practice/client authorization boundary.
# Upload documents through the scoped Documents workspace instead.
SUMMERNOTE_CONFIG = {
    'disable_attachment': True,
    'attachment_require_authentication': True,
}
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

GOOGLE_OAUTH_CLIENT_ID = os.getenv('GOOGLE_OAUTH_CLIENT_ID', '')
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET', '')
GOOGLE_OAUTH_REDIRECT_URI = os.getenv('GOOGLE_OAUTH_REDIRECT_URI', '')
FIELD_ENCRYPTION_KEY = os.getenv('FIELD_ENCRYPTION_KEY', '')

STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')
STRIPE_PRICE_PER_USER_MONTHLY = os.getenv('STRIPE_PRICE_PER_USER_MONTHLY', '')
STRIPE_PRICE_PER_USER_YEARLY = os.getenv('STRIPE_PRICE_PER_USER_YEARLY', '')
STRIPE_PRICE_IDS = {
    'solo': {
        'monthly': STRIPE_PRICE_PER_USER_MONTHLY or os.getenv('STRIPE_PRICE_SOLO_MONTHLY', ''),
        'yearly': STRIPE_PRICE_PER_USER_YEARLY or os.getenv('STRIPE_PRICE_SOLO_YEARLY', ''),
    },
    'group': {
        'monthly': STRIPE_PRICE_PER_USER_MONTHLY or os.getenv('STRIPE_PRICE_GROUP_MONTHLY', ''),
        'yearly': STRIPE_PRICE_PER_USER_YEARLY or os.getenv('STRIPE_PRICE_GROUP_YEARLY', ''),
    },
    'clinic': {
        'monthly': STRIPE_PRICE_PER_USER_MONTHLY or os.getenv('STRIPE_PRICE_CLINIC_MONTHLY', ''),
        'yearly': STRIPE_PRICE_PER_USER_YEARLY or os.getenv('STRIPE_PRICE_CLINIC_YEARLY', ''),
    },
}

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
]
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Production is served exclusively through HTTPS behind the host Nginx proxy.
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'false' if DEBUG else 'true').lower() == 'true'
SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'false' if DEBUG else 'true').lower() == 'true'
CSRF_COOKIE_SECURE = os.getenv('CSRF_COOKIE_SECURE', 'false' if DEBUG else 'true').lower() == 'true'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '0' if DEBUG else '31536000'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv('SECURE_HSTS_INCLUDE_SUBDOMAINS', 'false' if DEBUG else 'true').lower() == 'true'
SECURE_HSTS_PRELOAD = os.getenv('SECURE_HSTS_PRELOAD', 'false' if DEBUG else 'true').lower() == 'true'

EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '25'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'false').lower() == 'true'
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'false').lower() == 'true'
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'NuviaMy <noreply@nuviamy.com>')
SUPPORT_EMAIL = os.getenv('SUPPORT_EMAIL', 'support@nuviamy.com')

if DJANGO_ENVIRONMENT == 'production':
    validate_production_settings(globals())

# Staff MFA cannot be disabled through environment variables.
MFA_REQUIRED = True
SECURITY_IDLE_TIMEOUT = 15 * 60
SECURITY_ABSOLUTE_TIMEOUT = 8 * 60 * 60
SECURITY_CHALLENGE_TIMEOUT = 10 * 60
SECURITY_REAUTH_TIMEOUT = 5 * 60
SESSION_COOKIE_AGE = SECURITY_ABSOLUTE_TIMEOUT
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
