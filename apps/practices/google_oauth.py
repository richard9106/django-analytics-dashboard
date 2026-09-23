import json
import base64
from email.message import EmailMessage
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone


GOOGLE_BASE_SCOPES = ['openid', 'email', 'profile']
GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://openidconnect.googleapis.com/v1/userinfo'
GOOGLE_GMAIL_API_URL = 'https://gmail.googleapis.com/gmail/v1/users/me'
GOOGLE_CALENDAR_API_URL = 'https://www.googleapis.com/calendar/v3'


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


def refresh_google_access_token(integration):
    if integration.token_expires_at and integration.token_expires_at > timezone.now() + timezone.timedelta(minutes=2):
        return integration.access_token
    if not integration.refresh_token:
        return integration.access_token

    payload = urlencode({
        'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
        'client_secret': settings.GOOGLE_OAUTH_CLIENT_SECRET,
        'refresh_token': integration.refresh_token,
        'grant_type': 'refresh_token',
    }).encode()
    req = Request(GOOGLE_TOKEN_URL, data=payload, method='POST')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    with urlopen(req, timeout=20) as response:
        token_response = json.loads(response.read().decode())

    integration.access_token = token_response.get('access_token', integration.access_token)
    integration.token_expires_at = token_expiry_from_response(token_response)
    integration.save(update_fields=['access_token', 'token_expires_at', 'updated_at'])
    return integration.access_token


def google_api_request(integration, url, method='GET', data=None):
    access_token = refresh_google_access_token(integration)
    body = json.dumps(data).encode() if data is not None else None
    req = Request(url, data=body, method=method)
    req.add_header('Authorization', f'Bearer {access_token}')
    if data is not None:
        req.add_header('Content-Type', 'application/json')
    with urlopen(req, timeout=20) as response:
        content = response.read().decode()
    return json.loads(content) if content else {}


def list_gmail_messages(integration, max_results=10):
    query = urlencode({'maxResults': max_results, 'q': 'newer_than:30d'})
    listing = google_api_request(integration, f'{GOOGLE_GMAIL_API_URL}/messages?{query}')
    messages = []
    for item in listing.get('messages', []):
        detail_query = urlencode({'format': 'metadata', 'metadataHeaders': ['From', 'Subject', 'Date']}, doseq=True)
        detail = google_api_request(integration, f"{GOOGLE_GMAIL_API_URL}/messages/{item['id']}?{detail_query}")
        headers = {header['name'].lower(): header['value'] for header in detail.get('payload', {}).get('headers', [])}
        messages.append({
            'id': detail.get('id'),
            'from': headers.get('from', ''),
            'subject': headers.get('subject', '(No subject)'),
            'date': headers.get('date', ''),
            'snippet': detail.get('snippet', ''),
        })
    return messages


def send_gmail_message(integration, to_email, subject, body):
    message = EmailMessage()
    message['To'] = to_email
    message['From'] = integration.account_email
    message['Subject'] = subject
    message.set_content(body)
    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip('=')
    return google_api_request(integration, f'{GOOGLE_GMAIL_API_URL}/messages/send', method='POST', data={'raw': encoded})


def list_calendar_events(integration, max_results=10):
    query = urlencode({
        'calendarId': 'primary',
        'timeMin': timezone.now().isoformat(),
        'singleEvents': 'true',
        'orderBy': 'startTime',
        'maxResults': max_results,
    })
    data = google_api_request(integration, f'{GOOGLE_CALENDAR_API_URL}/calendars/primary/events?{query}')
    return [
        {
            'id': event.get('id'),
            'summary': event.get('summary', '(No title)'),
            'start': event.get('start', {}).get('dateTime') or event.get('start', {}).get('date'),
            'end': event.get('end', {}).get('dateTime') or event.get('end', {}).get('date'),
        }
        for event in data.get('items', [])
    ]
