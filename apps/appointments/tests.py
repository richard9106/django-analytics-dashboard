from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.appointments.models import Appointment
from apps.clients.models import Client
from apps.practices.models import Practice, TherapistProfile


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
