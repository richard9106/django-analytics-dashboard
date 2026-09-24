from datetime import timedelta
from unittest.mock import patch
from urllib.error import HTTPError

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.appointments.models import Appointment, PracticeWorkingHour
from apps.appointments.reminders import due_reminder_appointments, send_appointment_reminder
from apps.clients.models import Client
from apps.practices.models import ExternalIntegration, Practice, TherapistProfile


class AppointmentModelTests(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(name="Nuvia Wellness")
        self.user = get_user_model().objects.create_user(username="drsmith")
        self.therapist = TherapistProfile.objects.create(
            user=self.user,
            practice=self.practice,
            license_number="ABC123",
            license_state="CA",
        )
        self.client = Client.objects.create(
            practice=self.practice,
            primary_therapist=self.therapist,
            first_name="Ana",
            last_name="Perez",
        )
        self.starts_at = timezone.now() + timedelta(days=1)
        self.ends_at = self.starts_at + timedelta(minutes=50)

    def build_appointment(self, **overrides):
        data = {
            "practice": self.practice,
            "client": self.client,
            "therapist": self.therapist,
            "starts_at": self.starts_at,
            "ends_at": self.ends_at,
        }
        data.update(overrides)
        return Appointment(**data)

    def test_appointment_accepts_same_practice_client_and_therapist(self):
        appointment = self.build_appointment()

        appointment.full_clean()

    def test_appointment_rejects_end_before_start(self):
        appointment = self.build_appointment(
            ends_at=self.starts_at - timedelta(minutes=10),
        )

        with self.assertRaisesMessage(ValidationError, "The appointment must end after it starts."):
            appointment.full_clean()

    def test_appointment_rejects_client_from_other_practice(self):
        other_practice = Practice.objects.create(name="Other Clinic")
        other_client = Client.objects.create(
            practice=other_practice,
            first_name="Carlos",
            last_name="Rivera",
        )
        appointment = self.build_appointment(client=other_client)

        with self.assertRaisesMessage(ValidationError, "The client must belong to the same practice"):
            appointment.full_clean()

    def test_appointment_rejects_therapist_from_other_practice(self):
        other_practice = Practice.objects.create(name="Other Clinic")
        other_user = get_user_model().objects.create_user(username="othertherapist")
        other_therapist = TherapistProfile.objects.create(
            user=other_user,
            practice=other_practice,
            license_number="XYZ789",
            license_state="NY",
        )
        appointment = self.build_appointment(therapist=other_therapist)

        with self.assertRaisesMessage(ValidationError, "The therapist must belong to the same practice"):
            appointment.full_clean()

    def test_appointment_defaults_to_scheduled_and_not_synced(self):
        appointment = self.build_appointment()

        self.assertEqual(appointment.status, Appointment.Status.SCHEDULED)
        self.assertFalse(appointment.sync_enabled)
        self.assertEqual(appointment.sync_status, Appointment.SyncStatus.NOT_SYNCED)
        self.assertEqual(appointment.external_calendar_provider, Appointment.CalendarProvider.NONE)
        self.assertTrue(appointment.reminder_enabled)
        self.assertEqual(appointment.reminder_status, Appointment.ReminderStatus.PENDING)

    def test_appointment_can_store_google_calendar_metadata(self):
        appointment = self.build_appointment(
            sync_enabled=True,
            external_calendar_provider=Appointment.CalendarProvider.GOOGLE,
            external_calendar_id="primary",
            external_event_id="google-event-123",
            external_event_url="https://calendar.google.com/calendar/event?eid=abc123",
            sync_status=Appointment.SyncStatus.SYNCED,
        )

        appointment.full_clean()
        self.assertEqual(appointment.external_event_id, "google-event-123")

    def test_disabled_sync_cannot_be_marked_synced(self):
        appointment = self.build_appointment(
            sync_enabled=False,
            sync_status=Appointment.SyncStatus.SYNCED,
        )

        with self.assertRaisesMessage(ValidationError, "Disabled calendar sync cannot be marked"):
            appointment.full_clean()

    def test_disabled_reminder_cannot_be_marked_sent(self):
        appointment = self.build_appointment(
            reminder_enabled=False,
            reminder_status=Appointment.ReminderStatus.SENT,
        )

        with self.assertRaisesMessage(ValidationError, "Disabled reminders cannot be marked"):
            appointment.full_clean()

    def test_appointment_rejects_time_outside_configured_working_hours(self):
        PracticeWorkingHour.objects.create(
            practice=self.practice,
            weekday=self.starts_at.weekday(),
            starts_at="09:00",
            ends_at="17:00",
        )
        starts_at = timezone.localtime(self.starts_at).replace(hour=18, minute=0, second=0, microsecond=0)
        appointment = self.build_appointment(starts_at=starts_at, ends_at=starts_at + timedelta(minutes=50))

        with self.assertRaisesMessage(ValidationError, "working hours"):
            appointment.full_clean()

    def test_appointment_allows_time_inside_configured_working_hours(self):
        PracticeWorkingHour.objects.create(
            practice=self.practice,
            weekday=self.starts_at.weekday(),
            starts_at="09:00",
            ends_at="17:00",
        )
        starts_at = timezone.localtime(self.starts_at).replace(hour=10, minute=0, second=0, microsecond=0)
        appointment = self.build_appointment(starts_at=starts_at, ends_at=starts_at + timedelta(minutes=50))

        appointment.full_clean()

    def test_send_appointment_reminder_uses_connected_gmail(self):
        self.client.email = "client@example.com"
        self.client.save(update_fields=["email"])
        appointment = self.build_appointment(starts_at=timezone.now() + timedelta(hours=23), ends_at=timezone.now() + timedelta(hours=24))
        appointment.save()
        ExternalIntegration.objects.create(
            practice=self.practice,
            provider=ExternalIntegration.Provider.GOOGLE,
            status=ExternalIntegration.Status.CONNECTED,
            send_email_enabled=True,
            access_token="access-token",
            refresh_token="refresh-token",
        )

        with patch("apps.appointments.reminders.send_gmail_message") as send_email:
            sent = send_appointment_reminder(appointment)

        self.assertTrue(sent)
        appointment.refresh_from_db()
        self.assertEqual(appointment.reminder_status, Appointment.ReminderStatus.SENT)
        self.assertIsNotNone(appointment.reminder_sent_at)
        send_email.assert_called_once()
        self.assertEqual(send_email.call_args.args[1], "client@example.com")

    def test_due_reminder_appointments_returns_next_24_hours_only(self):
        due = self.build_appointment(starts_at=timezone.now() + timedelta(hours=23), ends_at=timezone.now() + timedelta(hours=24))
        due.save()
        later = self.build_appointment(starts_at=timezone.now() + timedelta(days=3), ends_at=timezone.now() + timedelta(days=3, minutes=50))
        later.save()

        self.assertIn(due, list(due_reminder_appointments()))
        self.assertNotIn(later, list(due_reminder_appointments()))


class AppointmentViewTests(TestCase):
    def create_practice_user(self, username='drsmith', practice_name='Nuvia Wellness'):
        user = get_user_model().objects.create_user(
            username=username,
            password='StrongPass123!',
            first_name='Laura',
            last_name='Smith',
        )
        practice = Practice.objects.create(name=practice_name)
        therapist = TherapistProfile.objects.create(
            user=user,
            practice=practice,
            license_number=f'{username}-12345',
            license_state='CA',
        )
        UserProfile.objects.create(
            user=user,
            practice=practice,
            role=UserProfile.Role.OWNER,
        )
        client = Client.objects.create(
            practice=practice,
            primary_therapist=therapist,
            first_name='Maya',
            last_name='Johnson',
        )
        return user, practice, therapist, client

    def test_appointment_list_requires_login(self):
        response = self.client.get(reverse('appointments:list'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('login')}?next={reverse('appointments:list')}")

    def test_appointment_create_requires_login(self):
        response = self.client.get(reverse('appointments:create'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('login')}?next={reverse('appointments:create')}")

    def test_appointment_list_is_scoped_to_user_practice(self):
        user, practice, therapist, client = self.create_practice_user()
        _other_user, other_practice, other_therapist, other_client = self.create_practice_user(
            username='otherdoc',
            practice_name='Other Practice',
        )
        other_client.first_name = 'Hidden'
        other_client.last_name = 'Client'
        other_client.save()
        starts_at = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0)
        Appointment.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
        )
        Appointment.objects.create(
            practice=other_practice,
            client=other_client,
            therapist=other_therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
        )

        self.client.force_login(user)
        response = self.client.get(reverse('appointments:list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Maya Johnson')
        self.assertNotContains(response, 'Hidden Client')

    def test_appointment_list_shows_calendar_create_and_edit_links(self):
        user, practice, therapist, client = self.create_practice_user()
        starts_at = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0)
        appointment = Appointment.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
        )

        self.client.force_login(user)
        response = self.client.get(reverse('appointments:list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Practice Calendar')
        self.assertContains(response, '<div class="calendar-weekday">Mon</div>', html=True)
        self.assertContains(response, 'id="client-create-modal"')
        self.assertContains(response, 'id="appointment-create-modal"')
        self.assertContains(response, reverse('appointments:create'))
        self.assertContains(response, 'Create appointment')
        self.assertContains(response, reverse('appointments:edit', args=[appointment.pk]))
        self.assertContains(response, f'id="appointment-modal-{appointment.pk}"')
        self.assertContains(response, 'Save changes')
        self.assertContains(response, 'Delete appointment')
        self.assertContains(response, f"{reverse('appointments:create')}?date={starts_at.date().isoformat()}")
        self.assertContains(response, 'aria-label="Add appointment on')
        self.assertContains(response, 'Google Calendar: Not Synced')
        self.assertContains(response, reverse('appointments:google_sync', args=[appointment.pk]))

    def test_appointment_list_highlights_today(self):
        user, _practice, _therapist, _client = self.create_practice_user()

        self.client.force_login(user)
        response = self.client.get(reverse('appointments:list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'calendar-day today')

    def test_appointment_create_saves_to_user_practice(self):
        user, practice, therapist, client = self.create_practice_user()
        starts_at = timezone.localtime().replace(hour=11, minute=0, second=0, microsecond=0) + timedelta(days=1)
        ends_at = starts_at + timedelta(minutes=50)

        self.client.force_login(user)
        response = self.client.post(reverse('appointments:create'), {
            'client': client.pk,
            'therapist': therapist.pk,
            'starts_at': starts_at.strftime('%Y-%m-%dT%H:%M'),
            'ends_at': ends_at.strftime('%Y-%m-%dT%H:%M'),
            'appointment_type': Appointment.AppointmentType.VIDEO,
            'status': Appointment.Status.SCHEDULED,
            'location': '',
            'meeting_url': 'https://example.com/session',
            'notes': 'Initial consultation.',
        })

        self.assertRedirects(response, reverse('appointments:list'))
        appointment = Appointment.objects.get()
        self.assertEqual(appointment.practice, practice)
        self.assertEqual(appointment.client, client)
        self.assertEqual(appointment.therapist, therapist)

    def test_appointment_create_can_create_weekly_recurring_series(self):
        user, practice, therapist, client = self.create_practice_user()
        starts_at = timezone.localtime().replace(hour=11, minute=0, second=0, microsecond=0) + timedelta(days=1)
        ends_at = starts_at + timedelta(minutes=50)

        self.client.force_login(user)
        response = self.client.post(reverse('appointments:create'), {
            'client': client.pk,
            'therapist': therapist.pk,
            'starts_at': starts_at.strftime('%Y-%m-%dT%H:%M'),
            'ends_at': ends_at.strftime('%Y-%m-%dT%H:%M'),
            'appointment_type': Appointment.AppointmentType.VIDEO,
            'status': Appointment.Status.SCHEDULED,
            'location': '',
            'meeting_url': '',
            'notes': 'Weekly session.',
            'repeat_weekly_count': '3',
        })

        self.assertRedirects(response, reverse('appointments:list'))
        appointments = list(Appointment.objects.filter(practice=practice).order_by('starts_at'))
        self.assertEqual(len(appointments), 3)
        self.assertEqual(appointments[1].starts_at, appointments[0].starts_at + timedelta(weeks=1))
        self.assertEqual(appointments[2].starts_at, appointments[0].starts_at + timedelta(weeks=2))

    def test_availability_settings_create_working_hour(self):
        user, practice, _therapist, _client = self.create_practice_user()
        self.client.force_login(user)

        response = self.client.post(reverse('practice_settings:working_hour_create'), {
            'weekday': PracticeWorkingHour.Weekday.MONDAY,
            'starts_at': '09:00',
            'ends_at': '17:00',
            'active': 'on',
        })

        self.assertRedirects(response, reverse('practice_settings:availability'))
        working_hour = PracticeWorkingHour.objects.get()
        self.assertEqual(working_hour.practice, practice)
        self.assertTrue(working_hour.active)

    def test_appointment_create_syncs_to_google_calendar_when_enabled(self):
        user, practice, therapist, client = self.create_practice_user()
        ExternalIntegration.objects.create(
            practice=practice,
            provider=ExternalIntegration.Provider.GOOGLE,
            status=ExternalIntegration.Status.CONNECTED,
            calendar_enabled=True,
            access_token='access-token',
            refresh_token='refresh-token',
        )
        starts_at = timezone.localtime().replace(hour=11, minute=0, second=0, microsecond=0) + timedelta(days=1)
        ends_at = starts_at + timedelta(minutes=50)

        self.client.force_login(user)
        with patch('apps.appointments.google_calendar.google_api_request') as google_request:
            google_request.return_value = {'id': 'google-event-123', 'htmlLink': 'https://calendar.google.com/event'}
            response = self.client.post(reverse('appointments:create'), {
                'client': client.pk,
                'therapist': therapist.pk,
                'starts_at': starts_at.strftime('%Y-%m-%dT%H:%M'),
                'ends_at': ends_at.strftime('%Y-%m-%dT%H:%M'),
                'appointment_type': Appointment.AppointmentType.VIDEO,
                'status': Appointment.Status.SCHEDULED,
                'location': 'Office 1',
                'meeting_url': '',
                'notes': 'Do not send notes to Google.',
            })

        self.assertRedirects(response, reverse('appointments:list'))
        appointment = Appointment.objects.get()
        self.assertTrue(appointment.sync_enabled)
        self.assertEqual(appointment.external_calendar_provider, Appointment.CalendarProvider.GOOGLE)
        self.assertEqual(appointment.external_event_id, 'google-event-123')
        self.assertEqual(appointment.sync_status, Appointment.SyncStatus.SYNCED)
        args, kwargs = google_request.call_args
        self.assertEqual(kwargs['method'], 'POST')
        self.assertIn('/calendars/primary/events', args[1])
        self.assertEqual(kwargs['data']['summary'], 'Appointment with Maya Johnson')
        self.assertNotIn('Do not send notes', kwargs['data']['description'])

    def test_appointment_create_prefills_from_calendar_date(self):
        user, _practice, _therapist, _client = self.create_practice_user()

        self.client.force_login(user)
        response = self.client.get(f"{reverse('appointments:create')}?date=2026-09-23")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="2026-09-23T09:00"')

    def test_appointment_create_rejects_client_from_another_practice(self):
        user, _practice, therapist, _client = self.create_practice_user()
        _other_user, _other_practice, _other_therapist, other_client = self.create_practice_user(
            username='otherdoc',
            practice_name='Other Practice',
        )
        starts_at = timezone.localtime().replace(hour=11, minute=0, second=0, microsecond=0) + timedelta(days=1)
        ends_at = starts_at + timedelta(minutes=50)

        self.client.force_login(user)
        response = self.client.post(reverse('appointments:create'), {
            'client': other_client.pk,
            'therapist': therapist.pk,
            'starts_at': starts_at.strftime('%Y-%m-%dT%H:%M'),
            'ends_at': ends_at.strftime('%Y-%m-%dT%H:%M'),
            'appointment_type': Appointment.AppointmentType.VIDEO,
            'status': Appointment.Status.SCHEDULED,
            'location': '',
            'meeting_url': '',
            'notes': '',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Select a valid choice')
        self.assertEqual(Appointment.objects.count(), 0)

    def test_appointment_update_saves_changes(self):
        user, practice, therapist, client = self.create_practice_user()
        starts_at = timezone.localtime().replace(hour=11, minute=0, second=0, microsecond=0) + timedelta(days=1)
        appointment = Appointment.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
        )
        updated_start = starts_at.replace(hour=14)
        updated_end = updated_start + timedelta(minutes=50)

        self.client.force_login(user)
        response = self.client.post(reverse('appointments:edit', args=[appointment.pk]), {
            'client': client.pk,
            'therapist': therapist.pk,
            'starts_at': updated_start.strftime('%Y-%m-%dT%H:%M'),
            'ends_at': updated_end.strftime('%Y-%m-%dT%H:%M'),
            'appointment_type': Appointment.AppointmentType.PHONE,
            'status': Appointment.Status.COMPLETED,
            'location': '',
            'meeting_url': '',
            'notes': 'Updated session.',
        })

        self.assertRedirects(response, reverse('appointments:list'))
        appointment.refresh_from_db()
        self.assertEqual(appointment.appointment_type, Appointment.AppointmentType.PHONE)
        self.assertEqual(appointment.status, Appointment.Status.COMPLETED)
        self.assertEqual(appointment.notes, 'Updated session.')

    def test_appointment_update_patches_google_calendar_event(self):
        user, practice, therapist, client = self.create_practice_user()
        ExternalIntegration.objects.create(
            practice=practice,
            provider=ExternalIntegration.Provider.GOOGLE,
            status=ExternalIntegration.Status.CONNECTED,
            calendar_enabled=True,
            access_token='access-token',
            refresh_token='refresh-token',
        )
        starts_at = timezone.localtime().replace(hour=11, minute=0, second=0, microsecond=0) + timedelta(days=1)
        appointment = Appointment.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
            sync_enabled=True,
            external_calendar_provider=Appointment.CalendarProvider.GOOGLE,
            external_calendar_id='primary',
            external_event_id='google-event-123',
            sync_status=Appointment.SyncStatus.SYNCED,
        )
        updated_start = starts_at.replace(hour=14)
        updated_end = updated_start + timedelta(minutes=50)

        self.client.force_login(user)
        with patch('apps.appointments.google_calendar.google_api_request') as google_request:
            google_request.return_value = {'id': 'google-event-123', 'htmlLink': 'https://calendar.google.com/event'}
            response = self.client.post(reverse('appointments:edit', args=[appointment.pk]), {
                'client': client.pk,
                'therapist': therapist.pk,
                'starts_at': updated_start.strftime('%Y-%m-%dT%H:%M'),
                'ends_at': updated_end.strftime('%Y-%m-%dT%H:%M'),
                'appointment_type': Appointment.AppointmentType.PHONE,
                'status': Appointment.Status.SCHEDULED,
                'location': '',
                'meeting_url': '',
                'notes': 'Updated session.',
            })

        self.assertRedirects(response, reverse('appointments:list'))
        appointment.refresh_from_db()
        self.assertEqual(appointment.sync_status, Appointment.SyncStatus.SYNCED)
        args, kwargs = google_request.call_args
        self.assertEqual(kwargs['method'], 'PATCH')
        self.assertIn('/calendars/primary/events/google-event-123', args[1])

    def test_google_sync_restores_event_deleted_from_google_calendar(self):
        user, practice, therapist, client = self.create_practice_user()
        ExternalIntegration.objects.create(
            practice=practice,
            provider=ExternalIntegration.Provider.GOOGLE,
            status=ExternalIntegration.Status.CONNECTED,
            calendar_enabled=True,
            access_token='access-token',
            refresh_token='refresh-token',
        )
        starts_at = timezone.localtime().replace(hour=11, minute=0, second=0, microsecond=0) + timedelta(days=1)
        appointment = Appointment.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
            sync_enabled=True,
            external_calendar_provider=Appointment.CalendarProvider.GOOGLE,
            external_calendar_id='primary',
            external_event_id='deleted-google-event',
            sync_status=Appointment.SyncStatus.SYNCED,
        )

        self.client.force_login(user)
        with patch('apps.appointments.google_calendar.google_api_request') as google_request:
            google_request.side_effect = [
                HTTPError('https://calendar.example/events/deleted-google-event', 404, 'Not Found', None, None),
                {'id': 'replacement-google-event', 'htmlLink': 'https://calendar.google.com/replacement'},
            ]
            response = self.client.post(reverse('appointments:google_sync', args=[appointment.pk]))

        self.assertRedirects(response, reverse('appointments:list'))
        appointment.refresh_from_db()
        self.assertEqual(appointment.external_event_id, 'replacement-google-event')
        self.assertEqual(appointment.sync_status, Appointment.SyncStatus.SYNCED)
        self.assertEqual(google_request.call_args_list[0].kwargs['method'], 'PATCH')
        self.assertEqual(google_request.call_args_list[1].kwargs['method'], 'POST')

    def test_google_sync_action_is_scoped_to_user_practice(self):
        user, _practice, _therapist, _client = self.create_practice_user()
        _other_user, other_practice, other_therapist, other_client = self.create_practice_user(
            username='otherdoc',
            practice_name='Other Practice',
        )
        starts_at = timezone.localtime().replace(hour=11, minute=0, second=0, microsecond=0) + timedelta(days=1)
        appointment = Appointment.objects.create(
            practice=other_practice,
            client=other_client,
            therapist=other_therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
        )

        self.client.force_login(user)
        response = self.client.post(reverse('appointments:google_sync', args=[appointment.pk]))

        self.assertEqual(response.status_code, 404)

    def test_appointment_edit_form_shows_delete_action(self):
        user, practice, therapist, client = self.create_practice_user()
        starts_at = timezone.localtime().replace(hour=11, minute=0, second=0, microsecond=0) + timedelta(days=1)
        appointment = Appointment.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
        )

        self.client.force_login(user)
        response = self.client.get(reverse('appointments:edit', args=[appointment.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Delete appointment')
        self.assertContains(response, reverse('appointments:delete', args=[appointment.pk]))

    def test_appointment_delete_removes_appointment(self):
        user, practice, therapist, client = self.create_practice_user()
        starts_at = timezone.localtime().replace(hour=11, minute=0, second=0, microsecond=0) + timedelta(days=1)
        appointment = Appointment.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
        )

        self.client.force_login(user)
        response = self.client.post(reverse('appointments:delete', args=[appointment.pk]))

        self.assertRedirects(response, reverse('appointments:list'))
        self.assertEqual(Appointment.objects.count(), 0)

    def test_appointment_delete_removes_google_calendar_event(self):
        user, practice, therapist, client = self.create_practice_user()
        ExternalIntegration.objects.create(
            practice=practice,
            provider=ExternalIntegration.Provider.GOOGLE,
            status=ExternalIntegration.Status.CONNECTED,
            calendar_enabled=True,
            access_token='access-token',
            refresh_token='refresh-token',
        )
        starts_at = timezone.localtime().replace(hour=11, minute=0, second=0, microsecond=0) + timedelta(days=1)
        appointment = Appointment.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
            sync_enabled=True,
            external_calendar_provider=Appointment.CalendarProvider.GOOGLE,
            external_calendar_id='primary',
            external_event_id='google-event-123',
            sync_status=Appointment.SyncStatus.SYNCED,
        )

        self.client.force_login(user)
        with patch('apps.appointments.google_calendar.google_api_request') as google_request:
            response = self.client.post(reverse('appointments:delete', args=[appointment.pk]))

        self.assertRedirects(response, reverse('appointments:list'))
        self.assertEqual(Appointment.objects.count(), 0)
        args, kwargs = google_request.call_args
        self.assertEqual(kwargs['method'], 'DELETE')
        self.assertIn('/calendars/primary/events/google-event-123', args[1])

    def test_appointment_update_is_scoped_to_user_practice(self):
        user, _practice, _therapist, _client = self.create_practice_user()
        _other_user, other_practice, other_therapist, other_client = self.create_practice_user(
            username='otherdoc',
            practice_name='Other Practice',
        )
        starts_at = timezone.localtime().replace(hour=11, minute=0, second=0, microsecond=0) + timedelta(days=1)
        appointment = Appointment.objects.create(
            practice=other_practice,
            client=other_client,
            therapist=other_therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
        )

        self.client.force_login(user)
        response = self.client.get(reverse('appointments:edit', args=[appointment.pk]))

        self.assertEqual(response.status_code, 404)

    def test_appointment_delete_is_scoped_to_user_practice(self):
        user, _practice, _therapist, _client = self.create_practice_user()
        _other_user, other_practice, other_therapist, other_client = self.create_practice_user(
            username='otherdoc',
            practice_name='Other Practice',
        )
        starts_at = timezone.localtime().replace(hour=11, minute=0, second=0, microsecond=0) + timedelta(days=1)
        appointment = Appointment.objects.create(
            practice=other_practice,
            client=other_client,
            therapist=other_therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
        )

        self.client.force_login(user)
        response = self.client.post(reverse('appointments:delete', args=[appointment.pk]))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Appointment.objects.count(), 1)
