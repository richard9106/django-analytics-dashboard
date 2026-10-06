"""Smoke-test a fresh deployment image without generating assets or using a DB."""
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django

django.setup()

from django.contrib.staticfiles.storage import staticfiles_storage
from django.test import Client

client = Client()
for asset in ('security-session.js', 'security.css', 'dashboard.css', 'favicon.svg', 'diagnosis-picker.js'):
    url = staticfiles_storage.url(asset)
    response = client.get(url, secure=True)
    if response.status_code != 200:
        raise RuntimeError(f'Packaged asset unavailable: {asset} (HTTP {response.status_code})')
    response.close()

if client.get('/login/', secure=True).status_code != 200:
    raise RuntimeError('Login page does not render from the deployment image.')
print('Packaged assets and login page are available in a fresh container.')
