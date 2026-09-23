import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone


GOOGLE_BASE_SCOPES = ['openid', 'email', 'profile']
GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://openidconnect.googleapis.com/v1/userinfo'


def get_google_redirect_uri(request):
    configured = getattr(settings, 'GOOGLE_OAUTH_REDIRECT_URI', '')
    if configured:
        return configured
    return request.build_absolute_uri('/settings/integrations/google/callback/')


def build_google_authorization_url(request, scopes, state):
    query = urlencode({
        'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
        'redirect_uri': get_google_redirect_uri(request),
        'response_type': 'code',
        'scope': ' '.join(GOOGLE_BASE_SCOPES + scopes),
        'access_type': 'offline',
        'prompt': 'consent',
        'state': state,
        'include_granted_scopes': 'true',
    })
    return f'{GOOGLE_AUTH_URL}?{query}'


def exchange_google_code(request, code):
    payload = urlencode({
        'code': code,
        'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
        'client_secret': settings.GOOGLE_OAUTH_CLIENT_SECRET,
        'redirect_uri': get_google_redirect_uri(request),
        'grant_type': 'authorization_code',
    }).encode()
    req = Request(GOOGLE_TOKEN_URL, data=payload, method='POST')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    with urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode())


def fetch_google_account_email(access_token):
    req = Request(GOOGLE_USERINFO_URL)
    req.add_header('Authorization', f'Bearer {access_token}')
    with urlopen(req, timeout=20) as response:
        data = json.loads(response.read().decode())
    return data.get('email', '')


def token_expiry_from_response(token_response):
    expires_in = token_response.get('expires_in')
    if not expires_in:
        return None
    return timezone.now() + timezone.timedelta(seconds=int(expires_in))
