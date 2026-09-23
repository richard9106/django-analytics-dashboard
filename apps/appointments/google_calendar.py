from urllib.parse import quote
from urllib.error import HTTPError

from django.utils import timezone

from apps.practices.google_oauth import GOOGLE_CALENDAR_API_URL, google_api_request
from apps.practices.models import ExternalIntegration

from .models import Appointment


def get_calendar_integration(practice):
    return ExternalIntegration.objects.filter(
        practice=practice,
        provider=ExternalIntegration.Provider.GOOGLE,
        status=ExternalIntegration.Status.CONNECTED,
        calendar_enabled=True,
    ).first()


def build_event_payload(appointment):
    description_parts = [
        'NuviaMy appointment.',
        f'Client: {appointment.client}',
        f'Therapist: {appointment.therapist}',
    ]
    if appointment.meeting_url:
        description_parts.append(f'Meeting URL: {appointment.meeting_url}')

    payload = {
        'summary': f'Appointment with {appointment.client}',
        'description': '\n'.join(description_parts),
        'start': {'dateTime': appointment.starts_at.isoformat()},
        'end': {'dateTime': appointment.ends_at.isoformat()},
    }
    if appointment.location:
        payload['location'] = appointment.location
    if appointment.status == Appointment.Status.CANCELLED:
        payload['status'] = 'cancelled'
    return payload


def sync_appointment_to_google(appointment):
    integration = get_calendar_integration(appointment.practice)
    if not integration:
        appointment.sync_enabled = False
        appointment.external_calendar_provider = Appointment.CalendarProvider.NONE
        appointment.sync_status = Appointment.SyncStatus.DISABLED
        appointment.sync_error = ''
        appointment.save(update_fields=['sync_enabled', 'external_calendar_provider', 'sync_status', 'sync_error', 'updated_at'])
        return

    appointment.sync_enabled = True
    appointment.external_calendar_provider = Appointment.CalendarProvider.GOOGLE
    appointment.external_calendar_id = 'primary'
    appointment.sync_status = Appointment.SyncStatus.PENDING
    appointment.sync_error = ''
    appointment.save(update_fields=[
        'sync_enabled',
        'external_calendar_provider',
        'external_calendar_id',
        'sync_status',
        'sync_error',
        'updated_at',
    ])

    try:
        payload = build_event_payload(appointment)
        if appointment.external_event_id:
            event_id = quote(appointment.external_event_id, safe='')
            try:
                data = google_api_request(integration, f'{GOOGLE_CALENDAR_API_URL}/calendars/primary/events/{event_id}', method='PATCH', data=payload)
            except HTTPError as error:
                if error.code != 404:
                    raise
                appointment.external_event_id = ''
                data = google_api_request(integration, f'{GOOGLE_CALENDAR_API_URL}/calendars/primary/events', method='POST', data=payload)
        else:
            data = google_api_request(integration, f'{GOOGLE_CALENDAR_API_URL}/calendars/primary/events', method='POST', data=payload)
        appointment.external_event_id = data.get('id', appointment.external_event_id)
        appointment.external_event_url = data.get('htmlLink', appointment.external_event_url)
        appointment.last_synced_at = timezone.now()
        appointment.sync_status = Appointment.SyncStatus.SYNCED
        appointment.sync_error = ''
    except Exception as error:
        appointment.sync_status = Appointment.SyncStatus.FAILED
        appointment.sync_error = str(error)
    appointment.save(update_fields=[
        'external_event_id',
        'external_event_url',
        'last_synced_at',
        'sync_status',
        'sync_error',
        'updated_at',
    ])


def delete_google_event_for_appointment(appointment):
    if not appointment.external_event_id:
        return
    integration = get_calendar_integration(appointment.practice)
    if not integration:
        return
    event_id = quote(appointment.external_event_id, safe='')
    google_api_request(integration, f'{GOOGLE_CALENDAR_API_URL}/calendars/primary/events/{event_id}', method='DELETE')
