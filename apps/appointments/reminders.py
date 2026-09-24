from django.utils import timezone

from apps.practices.google_oauth import send_gmail_message
from apps.practices.models import ExternalIntegration

from .models import Appointment


def get_gmail_integration(practice):
    return ExternalIntegration.objects.filter(
        practice=practice,
        provider=ExternalIntegration.Provider.GOOGLE,
        status=ExternalIntegration.Status.CONNECTED,
        send_email_enabled=True,
    ).first()


def build_reminder_message(appointment):
    local_start = timezone.localtime(appointment.starts_at)
    subject = f'Appointment reminder for {local_start:%A, %B %-d at %-I:%M %p}'
    therapist_name = appointment.therapist.user.get_full_name() or appointment.therapist.user.username
    lines = [
        f'Hi {appointment.client.first_name},',
        '',
        f'This is a reminder for your appointment with {therapist_name} on {local_start:%A, %B %-d at %-I:%M %p}.',
    ]
    if appointment.meeting_url:
        lines.extend(['', f'Meeting link: {appointment.meeting_url}'])
    elif appointment.location:
        lines.extend(['', f'Location: {appointment.location}'])
    lines.extend(['', 'If you need to make a change, please sign in to your NuviaMy portal or contact your practice.', '', 'NuviaMy'])
    return subject, '\n'.join(lines)


def send_appointment_reminder(appointment):
    if not appointment.reminder_enabled:
        appointment.reminder_status = Appointment.ReminderStatus.DISABLED
        appointment.save(update_fields=['reminder_status', 'updated_at'])
        return False
    if not appointment.client.email:
        appointment.reminder_status = Appointment.ReminderStatus.FAILED
        appointment.reminder_error = 'Client email is missing.'
        appointment.save(update_fields=['reminder_status', 'reminder_error', 'updated_at'])
        return False
    integration = get_gmail_integration(appointment.practice)
    if not integration:
        appointment.reminder_status = Appointment.ReminderStatus.FAILED
        appointment.reminder_error = 'Connected Gmail sending is not enabled.'
        appointment.save(update_fields=['reminder_status', 'reminder_error', 'updated_at'])
        return False

    try:
        subject, body = build_reminder_message(appointment)
        send_gmail_message(integration, appointment.client.email, subject, body)
        appointment.reminder_status = Appointment.ReminderStatus.SENT
        appointment.reminder_sent_at = timezone.now()
        appointment.reminder_error = ''
        appointment.save(update_fields=['reminder_status', 'reminder_sent_at', 'reminder_error', 'updated_at'])
        return True
    except Exception as error:
        appointment.reminder_status = Appointment.ReminderStatus.FAILED
        appointment.reminder_error = str(error)
        appointment.save(update_fields=['reminder_status', 'reminder_error', 'updated_at'])
        return False


def due_reminder_appointments(window_hours=24):
    now = timezone.now()
    window_end = now + timezone.timedelta(hours=window_hours)
    return Appointment.objects.filter(
        reminder_enabled=True,
        reminder_status__in=[Appointment.ReminderStatus.PENDING, Appointment.ReminderStatus.FAILED],
        reminder_sent_at__isnull=True,
        status=Appointment.Status.SCHEDULED,
        starts_at__gte=now,
        starts_at__lte=window_end,
    ).select_related('practice', 'client', 'therapist__user')
