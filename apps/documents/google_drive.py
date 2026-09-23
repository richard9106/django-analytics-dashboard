import json
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from django.utils import timezone

from apps.practices.google_oauth import google_api_request, refresh_google_access_token
from apps.practices.models import ExternalIntegration

from .models import ClientDocument


GOOGLE_DRIVE_API_URL = 'https://www.googleapis.com/drive/v3'
GOOGLE_DRIVE_UPLOAD_URL = 'https://www.googleapis.com/upload/drive/v3'


def get_drive_integration(practice):
    return ExternalIntegration.objects.filter(
        practice=practice,
        provider=ExternalIntegration.Provider.GOOGLE,
        status=ExternalIntegration.Status.CONNECTED,
        file_storage_enabled=True,
    ).first()


def drive_request(integration, url, method='GET', data=None, content_type='application/json'):
    access_token = refresh_google_access_token(integration)
    req = Request(url, data=data, method=method)
    req.add_header('Authorization', f'Bearer {access_token}')
    if data is not None:
        req.add_header('Content-Type', content_type)
    with urlopen(req, timeout=30) as response:
        content = response.read().decode()
    return json.loads(content) if content else {}


def get_or_create_drive_folder(integration):
    folder_name = integration.default_folder.strip()
    if not folder_name:
        return None
    escaped_name = folder_name.replace("'", "\\'")
    query = urlencode({
        'q': f"name = '{escaped_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        'fields': 'files(id,name)',
        'pageSize': 1,
    })
    existing = google_api_request(integration, f'{GOOGLE_DRIVE_API_URL}/files?{query}')
    files = existing.get('files', [])
    if files:
        return files[0]['id']
    created = google_api_request(
        integration,
        f'{GOOGLE_DRIVE_API_URL}/files',
        method='POST',
        data={'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'},
    )
    return created.get('id')


def upload_document_file(integration, document, folder_id=None):
    filename = document.original_filename or document.file.name.rsplit('/', 1)[-1]
    metadata = {'name': filename}
    if folder_id:
        metadata['parents'] = [folder_id]

    boundary = 'nuviamy-drive-boundary'
    with document.file.open('rb') as handle:
        file_bytes = handle.read()
    content_type = document.content_type or 'application/octet-stream'
    body = b''.join([
        f'--{boundary}\r\n'.encode(),
        b'Content-Type: application/json; charset=UTF-8\r\n\r\n',
        json.dumps(metadata).encode(),
        b'\r\n',
        f'--{boundary}\r\n'.encode(),
        f'Content-Type: {content_type}\r\n\r\n'.encode(),
        file_bytes,
        b'\r\n',
        f'--{boundary}--\r\n'.encode(),
    ])

    fields = 'id,webViewLink'
    if document.external_file_id:
        file_id = quote(document.external_file_id, safe='')
        url = f'{GOOGLE_DRIVE_UPLOAD_URL}/files/{file_id}?{urlencode({"uploadType": "multipart", "fields": fields})}'
        method = 'PATCH'
    else:
        url = f'{GOOGLE_DRIVE_UPLOAD_URL}/files?{urlencode({"uploadType": "multipart", "fields": fields})}'
        method = 'POST'
    return drive_request(integration, url, method=method, data=body, content_type=f'multipart/related; boundary={boundary}')


def export_document_to_google_drive(document):
    integration = get_drive_integration(document.practice)
    if not integration:
        document.external_storage_provider = ClientDocument.ExternalStorageProvider.NONE
        document.external_sync_status = ClientDocument.SyncStatus.DISABLED
        document.external_sync_error = 'Google Drive storage is not enabled.'
        document.save(update_fields=['external_storage_provider', 'external_sync_status', 'external_sync_error'])
        return

    document.external_storage_provider = ClientDocument.ExternalStorageProvider.GOOGLE_DRIVE
    document.external_sync_status = ClientDocument.SyncStatus.PENDING
    document.external_sync_error = ''
    document.save(update_fields=['external_storage_provider', 'external_sync_status', 'external_sync_error'])

    try:
        folder_id = get_or_create_drive_folder(integration)
        try:
            data = upload_document_file(integration, document, folder_id=folder_id)
        except HTTPError as error:
            if error.code != 404:
                raise
            document.external_file_id = ''
            data = upload_document_file(integration, document, folder_id=folder_id)
        document.external_file_id = data.get('id', document.external_file_id)
        document.external_file_url = data.get('webViewLink', document.external_file_url)
        document.external_synced_at = timezone.now()
        document.external_sync_status = ClientDocument.SyncStatus.SYNCED
        document.external_sync_error = ''
    except Exception as error:
        document.external_sync_status = ClientDocument.SyncStatus.FAILED
        document.external_sync_error = str(error)
    document.save(update_fields=[
        'external_file_id',
        'external_file_url',
        'external_synced_at',
        'external_sync_status',
        'external_sync_error',
    ])
