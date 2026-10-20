"""Shared S3/R2 settings; native AWS uses the SDK credential provider chain."""
from django.core.exceptions import ImproperlyConfigured


def cloud_storage_settings(env):
    backend = env.get('DJANGO_STORAGE_BACKEND', '')
    if backend not in {'s3', 'r2'}:
        return {}
    bucket = env.get('AWS_STORAGE_BUCKET_NAME', '').strip()
    if not bucket:
        raise ImproperlyConfigured('Cloud storage requires a bucket name.')
    access = env.get('AWS_ACCESS_KEY_ID') or None
    secret = env.get('AWS_SECRET_ACCESS_KEY') or None
    if bool(access) != bool(secret):
        raise ImproperlyConfigured('Configure both static credentials or neither for an instance role.')
    endpoint = env.get('AWS_S3_ENDPOINT_URL') or None
    if backend == 's3' and endpoint:
        raise ImproperlyConfigured('Native S3 must use AWS endpoints; remove the R2 endpoint.')
    if backend == 'r2' and not endpoint:
        raise ImproperlyConfigured('R2 requires its endpoint.')
    region = env.get('AWS_S3_REGION_NAME') or ('us-east-1' if backend == 's3' else 'auto')
    if backend == 's3' and region == 'auto':
        raise ImproperlyConfigured('Native S3 requires an explicit AWS region.')
    return {'AWS_ACCESS_KEY_ID': access, 'AWS_SECRET_ACCESS_KEY': secret,
            'AWS_SESSION_TOKEN': env.get('AWS_SESSION_TOKEN') or None,
            'AWS_STORAGE_BUCKET_NAME': bucket, 'AWS_S3_ENDPOINT_URL': endpoint,
            'AWS_S3_REGION_NAME': region, 'AWS_S3_SIGNATURE_VERSION': 's3v4',
            'AWS_S3_ADDRESSING_STYLE': 'virtual' if backend == 's3' else 'path',
            'AWS_DEFAULT_ACL': None, 'AWS_QUERYSTRING_AUTH': True,
            'AWS_S3_FILE_OVERWRITE': False}
