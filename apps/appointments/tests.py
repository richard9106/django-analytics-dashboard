from datetime import datetime, time, timedelta
from uuid import uuid4
from unittest.mock import patch
from urllib.error import HTTPError

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.audit.models import AuditLog
from apps.appointments.models import Appointment, PracticeAvailabilityOverride, PracticeWorkingHour
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

    def test_appointment_rejects_day_without_a_configured_range(self):
        configured_day = timezone.localtime(self.starts_at).weekday()
        PracticeWorkingHour.objects.create(
            practice=self.practice,
            weekday=configured_day,
            starts_at="09:00",
            ends_at="17:00",
        )
        local_start = timezone.localtime(self.starts_at) + timedelta(days=1)
        local_start = local_start.replace(hour=10, minute=0, second=0, microsecond=0)
        appointment = self.build_appointment(
            starts_at=local_start,
            ends_at=local_start + timedelta(minutes=50),
        )

        with self.assertRaisesMessage(ValidationError, "working hours"):
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


@override_settings(MFA_REQUIRED=False)
class AppointmentViewTests(TestCase):
    def test_session_links_prefill_note_and_invoice_and_return_after_saving(self):
        from apps.billing.models import Invoice
        from apps.clinical.models import SessionNote
        user, practice, therapist, client = self.create_practice_user()
        start = timezone.now() + timedelta(days=1)
        appointment = Appointment.objects.create(practice=practice, client=client, therapist=therapist, starts_at=start, ends_at=start + timedelta(minutes=50))
        self.client.force_login(user)
        session_url = reverse('appointments:edit', args=[appointment.pk])
        page = self.client.get(session_url)
        self.assertContains(page, 'Create note')
        self.assertContains(page, 'Create invoice')
        note_url = reverse('clinical:create') + f'?appointment={appointment.pk}'
        invoice_url = reverse('billing:invoice_create') + f'?appointment={appointment.pk}'
        for url in (note_url, invoice_url):
            page = self.client.get(url)
            self.assertEqual(page.context['form'].initial['client'], client.pk)
            self.assertEqual(page.context['form'].initial['appointment'], appointment.pk)
        response = self.client.post(note_url, {'client': client.pk, 'therapist': therapist.pk, 'appointment': appointment.pk, 'note_type': SessionNote.NoteType.PROGRESS_NOTE, 'content': 'Session follow-up.'})
        self.assertRedirects(response, session_url)
        self.assertEqual(SessionNote.objects.get().appointment, appointment)
        response = self.client.post(invoice_url, {'client': client.pk, 'appointment': appointment.pk, 'amount': '150.00', 'status': Invoice.Status.DRAFT})
        self.assertRedirects(response, session_url)
        invoice = Invoice.objects.get()
        self.assertEqual(invoice.appointment, appointment)
        self.assertEqual(invoice.status, Invoice.Status.DRAFT)
        self.assertIsNone(invoice.paid_at)

    def test_workflow_prefill_rejects_foreign_or_invalid_session(self):
        user, practice, therapist, client = self.create_practice_user()
        other_user, other, other_therapist, other_client = self.create_practice_user(username='otherdoc')
        start = timezone.now()
        foreign = Appointment.objects.create(practice=other, client=other_client, therapist=other_therapist, starts_at=start, ends_at=start + timedelta(minutes=50))
        self.client.force_login(user)
        for name in ('clinical:create', 'billing:invoice_create'):
            for value in (str(foreign.pk), 'invalid', '9' * 50):
                self.assertEqual(self.client.get(reverse(name), {'appointment': value}).status_code, 404)
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_session_invoice_review_filters_records(self):
        from apps.billing.models import Invoice
        user, practice, therapist, client = self.create_practice_user()
        start = timezone.now()
        appointment = Appointment.objects.create(practice=practice, client=client, therapist=therapist, starts_at=start, ends_at=start + timedelta(minutes=50))
        linked = Invoice.objects.create(practice=practice, client=client, appointment=appointment, invoice_number='SESSION-1', amount=150)
        Invoice.objects.create(practice=practice, client=client, invoice_number='UNRELATED-1', amount=150)
        self.client.force_login(user)
        response = self.client.get(reverse('billing:list'), {'appointment': appointment.pk})
        self.assertEqual(list(response.context['invoices']), [linked])
        response = self.client.get(reverse('billing:list'), {'appointment': 'invalid'})
        self.assertEqual(list(response.context['invoices']), [])

    def test_new_appointment_client_prefill_is_practice_scoped(self):
        user, practice, therapist, client = self.create_practice_user()
        client.primary_therapist = therapist
        client.save()
        _other_user, _other_practice, _other_therapist, other_client = self.create_practice_user(username='other-prefill')
        self.client.force_login(user)
        url = reverse('appointments:create')
        response = self.client.get(url, {'client': client.pk})
        self.assertEqual(response.context['form'].initial['client'], client.pk)
        self.assertEqual(response.context['form'].initial['therapist'], therapist.pk)
        for value in [str(other_client.pk), 'bad', '9' * 30]:
            response = self.client.get(url, {'client': value})
            self.assertNotIn('client', response.context['form'].initial)

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

    def test_sync_issues_are_practice_scoped_and_hide_provider_error(self):
        user, practice, therapist, client = self.create_practice_user()
        _other_user, other_practice, other_therapist, other_client = self.create_practice_user(
            username='otherdoc', practice_name='Other Practice')
        Appointment.objects.create(practice=practice, client=client, therapist=therapist,
                                   starts_at=timezone.now(), ends_at=timezone.now() + timedelta(minutes=50),
                                   sync_enabled=True, sync_status=Appointment.SyncStatus.FAILED,
                                   sync_error='provider secret details')
        Appointment.objects.create(practice=other_practice, client=other_client, therapist=other_therapist,
                                   starts_at=timezone.now(), ends_at=timezone.now() + timedelta(minutes=50),
                                   sync_enabled=True, sync_status=Appointment.SyncStatus.FAILED)
        self.client.force_login(user)
        response = self.client.get(reverse('appointments:sync_issues'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Maya Johnson')
        self.assertNotContains(response, 'provider secret details')
        self.assertNotContains(response, 'Other Practice')
        self.assertContains(response, reverse('practice_settings:integrations'))

    def test_sync_issue_retry_is_audited_and_redirects_back(self):
        user, practice, therapist, client = self.create_practice_user()
        appointment = Appointment.objects.create(practice=practice, client=client, therapist=therapist,
            starts_at=timezone.now(), ends_at=timezone.now() + timedelta(minutes=50),
            sync_enabled=True, sync_status=Appointment.SyncStatus.FAILED)
        self.client.force_login(user)
        with patch('apps.appointments.views.sync_appointment_to_google') as sync:
            sync.side_effect = lambda item: setattr(item, 'sync_status', Appointment.SyncStatus.SYNCED)
            response = self.client.post(reverse('appointments:google_sync', args=[appointment.pk]),
                                        {'next': reverse('appointments:sync_issues')})
        self.assertRedirects(response, reverse('appointments:sync_issues'))
        self.assertTrue(AuditLog.objects.filter(practice=practice, object_id=str(appointment.pk),
            metadata__calendar_sync_retry=True).exists())

    def test_recurring_conflict_rolls_back_every_session_and_preserves_form(self):
        user, practice, therapist, client = self.create_practice_user()
        starts = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)
        existing = Appointment.objects.create(practice=practice, client=client, therapist=therapist,
            starts_at=starts + timedelta(weeks=2), ends_at=starts + timedelta(weeks=2, minutes=50))
        self.client.force_login(user)
        with patch('apps.appointments.views.sync_appointment_to_google') as sync:
            response = self.client.post(reverse('appointments:create'), {
                'client': client.pk, 'therapist': therapist.pk, 'starts_at': starts.strftime('%Y-%m-%dT%H:%M'),
                'ends_at': (starts + timedelta(minutes=50)).strftime('%Y-%m-%dT%H:%M'),
                'appointment_type': 'video', 'status': 'scheduled', 'notes': 'Retain entered details',
                'repeat_weekly_count': 3, 'next': '/appointments/?view=agenda&status=scheduled',
            })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'overlapping')
        self.assertContains(response, 'Retain entered details')
        self.assertEqual(list(Appointment.objects.values_list('pk', flat=True)), [existing.pk])
        self.assertFalse(sync.called)

    def test_create_and_edit_preserve_calendar_context_and_reject_external_return(self):
        user, practice, therapist, client = self.create_practice_user()
        starts = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)
        data = {'client': client.pk, 'therapist': therapist.pk, 'starts_at': starts.strftime('%Y-%m-%dT%H:%M'),
                'ends_at': (starts + timedelta(minutes=50)).strftime('%Y-%m-%dT%H:%M'),
                'appointment_type': 'video', 'status': 'scheduled', 'next': '/appointments/?view=agenda&date=2026-10-06&q=Ana'}
        self.client.force_login(user)
        response = self.client.post(reverse('appointments:create'), data)
        self.assertEqual(response.url, data['next'])
        session = Appointment.objects.get(practice=practice)
        response = self.client.post(reverse('appointments:edit', args=[session.pk]), data)
        self.assertEqual(response.url, data['next'])
        for value in ['https://evil.example/appointments/', '//evil.example/appointments/', '/clients/', '/appointments/../clients/']:
            response = self.client.get(reverse('appointments:edit', args=[session.pk]), {'next': value})
            self.assertEqual(response.context['calendar_return_url'], reverse('appointments:list'))

    def test_cancel_is_post_only_scoped_and_preserves_record_even_when_hours_change(self):
        user, practice, therapist, client = self.create_practice_user()
        starts = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)
        session = Appointment.objects.create(practice=practice, client=client, therapist=therapist,
            starts_at=starts, ends_at=starts + timedelta(minutes=80))
        PracticeAvailabilityOverride.objects.create(practice=practice, date=starts.date(), is_available=False)
        self.client.force_login(user)
        url = reverse('appointments:cancel', args=[session.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        with patch('apps.appointments.views.delete_google_event_for_appointment') as sync:
            response = self.client.post(url, {'next': '/appointments/?view=agenda'})
            sync.assert_called_once()
        self.assertEqual(response.url, '/appointments/?view=agenda')
        session.refresh_from_db()
        self.assertEqual(session.status, Appointment.Status.CANCELLED)
        self.assertEqual(session.duration_minutes, 80)
        self.client.post(url)
        self.assertEqual(Appointment.objects.count(), 1)
        other_user, _, _, _ = self.create_practice_user(username='different-cancel')
        self.client.force_login(other_user)
        self.assertEqual(self.client.post(url).status_code, 404)

    def test_agenda_uses_visible_week_and_keeps_navigation_filters(self):
        user, practice, therapist, client = self.create_practice_user()
        starts = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0)
        session = Appointment.objects.create(practice=practice, client=client, therapist=therapist,
            starts_at=starts, ends_at=starts + timedelta(minutes=50))
        self.client.force_login(user)
        response = self.client.get(reverse('appointments:list'), {'view': 'agenda', 'date': starts.date().isoformat(), 'status': 'scheduled'})
        self.assertEqual(response.status_code, 200)
        days = response.context['calendar_agenda_days']
        self.assertEqual(len(days), 7)
        self.assertEqual(days[0]['date'].weekday(), 0)
        self.assertIn(session, [a for day in days for a in day['appointments']])
        self.assertIn('view=agenda', response.context['next_period_url'])
        self.assertIn('status=scheduled', response.context['next_period_url'])

    def test_read_only_calendar_hides_mutating_controls(self):
        user, practice, therapist, client = self.create_practice_user()
        profile = user.nuvia_profile
        profile.role = UserProfile.Role.THERAPIST
        profile.permissions = {'appointments': {'view': True}, 'clients': {'view': True}}
        profile.save()
        starts = timezone.now()
        session = Appointment.objects.create(practice=practice, therapist=therapist, client=client,
            starts_at=starts, ends_at=starts + timedelta(minutes=50))
        self.client.force_login(user)
        response = self.client.get(reverse('appointments:list'), {'view': 'agenda'})
        self.assertContains(response, reverse('clients:detail', args=[client.pk]))
        self.assertNotContains(response, 'data-draggable-appointment')
        self.assertNotContains(response, 'id="appointment-create-modal"')
        self.assertNotContains(response, f'id="appointment-modal-{session.pk}"')
        response = self.client.post(reverse('appointments:cancel', args=[session.pk]))
        session.refresh_from_db()
        self.assertEqual(session.status, Appointment.Status.SCHEDULED)
        self.assertNotEqual(response.status_code, 200)

    def test_agenda_markup_is_outside_navigation_and_google_is_optional(self):
        from html.parser import HTMLParser
        class Parser(HTMLParser):
            def handle_starttag(self, tag, attrs):
                for _, value in attrs:
                    if value:
                        assert '<' not in value, 'Markup leaked into an HTML attribute'
        user, _, _, _ = self.create_practice_user()
        self.client.force_login(user)
        for view in ['day', 'week', 'month', 'agenda']:
            response = self.client.get(reverse('appointments:list'), {'view': view})
            html = response.content.decode()
            Parser().feed(html)
            tabs = html.split('aria-label="Calendar views"', 1)[1].split('</nav>', 1)[0]
            self.assertEqual(tabs.count('class="active"'), 1)
            self.assertNotIn('calendar-agenda', tabs)
            self.assertEqual('class="calendar-agenda"' in html, view == 'agenda')
            self.assertNotIn('Sync to Google', html)

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
        self.assertContains(response, 'Day')
        self.assertContains(response, 'Week')
        self.assertContains(response, 'Month')
        self.assertNotContains(response, '>Year<')
        self.assertContains(response, 'Week appointment schedule')
        self.assertContains(response, 'gcal-week-columns')
        self.assertContains(response, 'id="client-create-modal"')
        self.assertContains(response, 'id="appointment-create-modal"')
        self.assertContains(response, reverse('appointments:create'))
        self.assertContains(response, 'Create appointment')
        self.assertContains(response, reverse('appointments:edit', args=[appointment.pk]))
        self.assertContains(response, reverse('appointments:reschedule', args=[appointment.pk]))
        self.assertContains(response, 'draggable="true"')
        self.assertContains(response, 'id="reschedule-modal"')
        self.assertContains(response, f'id="appointment-modal-{appointment.pk}"')
        self.assertContains(response, 'Save changes')
        self.assertContains(response, 'Delete appointment')
        self.assertContains(response, f"{reverse('appointments:create')}?date={starts_at.date().isoformat()}")
        self.assertContains(response, 'aria-label="Add appointment on')
        self.assertNotContains(response, 'Upcoming appointments')
        self.assertNotContains(response, reverse('appointments:google_sync', args=[appointment.pk]))
        self.assertContains(response, f'?view=week&amp;date={timezone.localdate().isoformat()}')
        ExternalIntegration.objects.create(practice=practice, provider=ExternalIntegration.Provider.GOOGLE,
            status=ExternalIntegration.Status.CONNECTED, calendar_enabled=True)
        response = self.client.get(reverse('appointments:list'))
        self.assertContains(response, reverse('appointments:google_sync', args=[appointment.pk]))

    def test_calendar_can_search_by_client_and_filter_status(self):
        user, practice, therapist, client = self.create_practice_user()
        hidden_client = Client.objects.create(practice=practice, first_name='Hidden', last_name='Client')
        starts_at = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0)
        visible_appointment = Appointment.objects.create(practice=practice, client=client, therapist=therapist, starts_at=starts_at, ends_at=starts_at + timedelta(minutes=50), status=Appointment.Status.SCHEDULED)
        hidden_appointment = Appointment.objects.create(practice=practice, client=hidden_client, therapist=therapist, starts_at=starts_at + timedelta(hours=1), ends_at=starts_at + timedelta(hours=1, minutes=50), status=Appointment.Status.CANCELLED)

        self.client.force_login(user)
        response = self.client.get(reverse('appointments:list'), {'q': 'Maya', 'status': Appointment.Status.SCHEDULED})

        self.assertEqual(response.status_code, 200)
        self.assertIn(visible_appointment, response.context['appointments'])
        self.assertNotIn(hidden_appointment, response.context['appointments'])
        self.assertContains(response, 'More filters')
        self.assertContains(response, 'value="scheduled" selected')

    def test_appointment_calendar_supports_day_week_and_month_views(self):
        user, practice, therapist, client = self.create_practice_user()
        starts_at = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0)
        Appointment.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
        )

        self.client.force_login(user)
        day_response = self.client.get(reverse('appointments:list'), {'view': 'day', 'date': starts_at.date().isoformat()})
        week_response = self.client.get(reverse('appointments:list'), {'view': 'week', 'date': starts_at.date().isoformat()})
        month_response = self.client.get(reverse('appointments:list'), {'view': 'month', 'month': starts_at.strftime('%Y-%m')})

        self.assertContains(day_response, 'Day appointment schedule')
        self.assertContains(day_response, 'calendar-grid-config')
        self.assertContains(day_response, 'gcal-day-column')
        self.assertContains(day_response, 'Maya Johnson')
        self.assertContains(week_response, 'Week appointment schedule')
        self.assertContains(week_response, 'gcal-week-columns')
        self.assertContains(week_response, 'Maya Johnson')
        self.assertContains(month_response, 'calendar-day')
        self.assertNotContains(month_response, 'Year appointment overview')

    def test_day_calendar_shows_unavailable_time_blocks(self):
        user, practice, _therapist, _client = self.create_practice_user()
        monday = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
        PracticeWorkingHour.objects.create(
            practice=practice,
            weekday=PracticeWorkingHour.Weekday.MONDAY,
            starts_at=time(9, 0),
            ends_at=time(17, 0),
        )

        self.client.force_login(user)
        response = self.client.get(reverse('appointments:list'), {'view': 'day', 'date': monday.isoformat()})

        self.assertContains(response, 'availability-block')
        self.assertContains(response, 'Unavailable')
        self.assertContains(response, 'data-availability-configured="1"')
        self.assertContains(response, 'data-availability-ranges="540-1020"')
        self.assertContains(response, 'data-availability-prompt')
        self.assertContains(response, 'name="end_date"')

    def test_appointment_reschedule_updates_start_and_end(self):
        user, _practice, therapist, client = self.create_practice_user()
        starts_at = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)
        appointment = Appointment.objects.create(
            practice=client.practice,
            client=client,
            therapist=therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
        )
        new_date = (starts_at + timedelta(days=2)).date()

        self.client.force_login(user)
        response = self.client.post(reverse('appointments:reschedule', args=[appointment.pk]), {
            'date': new_date.isoformat(),
            'time': '14:30',
        })

        self.assertRedirects(response, reverse('appointments:list'))
        appointment.refresh_from_db()
        self.assertEqual(timezone.localtime(appointment.starts_at).date(), new_date)
        self.assertEqual(timezone.localtime(appointment.starts_at).strftime('%H:%M'), '14:30')
        self.assertEqual(appointment.ends_at - appointment.starts_at, timedelta(minutes=50))

    def test_appointment_reschedule_returns_to_current_calendar_view(self):
        user, _practice, therapist, client = self.create_practice_user()
        starts_at = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)
        appointment = Appointment.objects.create(
            practice=client.practice,
            client=client,
            therapist=therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
        )
        return_url = f"{reverse('appointments:list')}?view=week&date={starts_at.date().isoformat()}"

        self.client.force_login(user)
        response = self.client.post(reverse('appointments:reschedule', args=[appointment.pk]), {
            'date': starts_at.date().isoformat(),
            'time': '15:00',
            'next': return_url,
        })

        self.assertRedirects(response, return_url)

    def test_appointment_reschedule_is_scoped_to_user_practice(self):
        user, _practice, _therapist, _client = self.create_practice_user()
        _other_user, other_practice, other_therapist, other_client = self.create_practice_user(
            username='otherdoc',
            practice_name='Other Practice',
        )
        starts_at = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)
        other_appointment = Appointment.objects.create(
            practice=other_practice,
            client=other_client,
            therapist=other_therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=50),
        )

        self.client.force_login(user)
        response = self.client.post(reverse('appointments:reschedule', args=[other_appointment.pk]), {
            'date': starts_at.date().isoformat(),
            'time': '14:30',
        })

        self.assertEqual(response.status_code, 404)

    def test_appointment_list_highlights_today(self):
        user, _practice, _therapist, _client = self.create_practice_user()

        self.client.force_login(user)
        response = self.client.get(reverse('appointments:list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'gcal-day-column today')

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

    def test_appointment_create_outside_configured_day_returns_form_error_not_500(self):
        user, practice, therapist, client = self.create_practice_user()
        target_date = timezone.localdate() + timedelta(days=1)
        PracticeWorkingHour.objects.create(
            practice=practice,
            weekday=(target_date.weekday() + 1) % 7,
            starts_at='09:00',
            ends_at='17:00',
        )
        starts_at = timezone.make_aware(datetime.combine(target_date, time(10, 0)))
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
            'notes': '',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'working hours')
        self.assertEqual(Appointment.objects.count(), 0)

    def test_date_availability_override_allows_specific_day(self):
        user, practice, therapist, client = self.create_practice_user()
        target_date = timezone.localdate() + timedelta(days=1)
        PracticeWorkingHour.objects.create(
            practice=practice,
            weekday=(target_date.weekday() + 1) % 7,
            starts_at='09:00',
            ends_at='17:00',
        )
        PracticeAvailabilityOverride.objects.create(
            practice=practice,
            date=target_date,
            starts_at=time(12, 0),
            ends_at=time(15, 0),
            is_available=True,
        )
        starts_at = timezone.make_aware(datetime.combine(target_date, time(13, 0)))
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
            'notes': '',
        })

        self.assertRedirects(response, reverse('appointments:list'))
        self.assertEqual(Appointment.objects.filter(practice=practice).count(), 1)

    def test_full_day_unavailable_override_blocks_appointments(self):
        user, practice, therapist, client = self.create_practice_user()
        target_date = timezone.localdate() + timedelta(days=1)
        PracticeWorkingHour.objects.create(
            practice=practice,
            weekday=target_date.weekday(),
            starts_at='09:00',
            ends_at='17:00',
        )
        PracticeAvailabilityOverride.objects.create(
            practice=practice,
            date=target_date,
            is_available=False,
        )
        starts_at = timezone.make_aware(datetime.combine(target_date, time(10, 0)))
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
            'notes': '',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'working hours')
        self.assertEqual(Appointment.objects.filter(practice=practice).count(), 0)

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
        self.assertIsNotNone(appointments[0].series_id)
        self.assertEqual({appointment.series_id for appointment in appointments}, {appointments[0].series_id})
        self.assertEqual(appointments[1].starts_at, appointments[0].starts_at + timedelta(weeks=1))
        self.assertEqual(appointments[2].starts_at, appointments[0].starts_at + timedelta(weeks=2))

    def test_series_cancel_only_cancels_current_and_future_occurrences(self):
        user, practice, therapist, client = self.create_practice_user()
        series_id = uuid4()
        starts_at = timezone.now() + timedelta(days=1)
        appointments = [
            Appointment.objects.create(
                practice=practice, client=client, therapist=therapist,
                starts_at=starts_at + timedelta(weeks=index), ends_at=starts_at + timedelta(weeks=index, minutes=50),
                series_id=series_id,
            ) for index in range(3)
        ]
        self.client.force_login(user)

        response = self.client.post(reverse('appointments:series_cancel', args=[appointments[1].pk]))

        self.assertRedirects(response, reverse('appointments:list'))
        appointments[0].refresh_from_db()
        appointments[1].refresh_from_db()
        appointments[2].refresh_from_db()
        self.assertEqual(appointments[0].status, Appointment.Status.SCHEDULED)
        self.assertEqual(appointments[1].status, Appointment.Status.CANCELLED)
        self.assertEqual(appointments[2].status, Appointment.Status.CANCELLED)

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

    def test_availability_settings_show_tree_actions(self):
        user, practice, _therapist, _client = self.create_practice_user()
        PracticeWorkingHour.objects.create(
            practice=practice,
            weekday=PracticeWorkingHour.Weekday.MONDAY,
            starts_at="09:00",
            ends_at="17:00",
            active=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('practice_settings:availability'))

        self.assertContains(response, 'role="region" aria-labelledby="availability-ranges-heading"')
        self.assertContains(response, '<th scope="col">Day</th>', html=True)
        self.assertContains(response, 'data-row-actions-trigger')
        self.assertContains(response, 'aria-controls="availability-actions-')
        self.assertContains(response, 'data-confirm-message="Delete this working-hours range? Scheduling availability will update immediately."')

    def test_calendar_availability_create_repeats_weekly(self):
        user, practice, _therapist, _client = self.create_practice_user()
        target_date = timezone.localdate() + timedelta(days=1)

        self.client.force_login(user)
        response = self.client.post(reverse('appointments:availability_create'), {
            'date': target_date.isoformat(),
            'is_available': 'on',
            'starts_at': '10:00',
            'ends_at': '14:00',
            'repeat': 'weekly',
            'repeat_count': '3',
            'note': 'Short clinic day',
        })

        self.assertRedirects(response, reverse('appointments:list'))
        overrides = list(PracticeAvailabilityOverride.objects.filter(practice=practice).order_by('date'))
        self.assertEqual(len(overrides), 3)
        self.assertEqual(overrides[1].date, target_date + timedelta(weeks=1))
        self.assertEqual(overrides[2].date, target_date + timedelta(weeks=2))
        self.assertTrue(practice.audit_logs.filter(action=AuditLog.Action.CREATE, object_type='appointments.PracticeAvailabilityOverride').exists())

    def test_calendar_availability_create_date_range(self):
        user, practice, _therapist, _client = self.create_practice_user()
        target_date = timezone.localdate() + timedelta(days=1)

        self.client.force_login(user)
        response = self.client.post(reverse('appointments:availability_create'), {
            'date': target_date.isoformat(),
            'end_date': (target_date + timedelta(days=2)).isoformat(),
            'is_available': 'on',
            'starts_at': '09:00',
            'ends_at': '12:00',
            'repeat': 'weekly',
            'repeat_count': '4',
        })

        self.assertRedirects(response, reverse('appointments:list'))
        overrides = list(PracticeAvailabilityOverride.objects.filter(practice=practice).order_by('date'))
        self.assertEqual(len(overrides), 3)
        self.assertEqual([override.date for override in overrides], [target_date, target_date + timedelta(days=1), target_date + timedelta(days=2)])

    def test_calendar_availability_is_scoped_to_user_practice(self):
        user, practice, _therapist, _client = self.create_practice_user()
        _other_user, other_practice, _other_therapist, _other_client = self.create_practice_user(
            username='otherdoc',
            practice_name='Other Practice',
        )

        self.client.force_login(user)
        response = self.client.post(reverse('appointments:availability_create'), {
            'date': (timezone.localdate() + timedelta(days=1)).isoformat(),
            'is_available': 'on',
            'starts_at': '10:00',
            'ends_at': '14:00',
            'repeat': 'none',
            'repeat_count': '1',
        })

        self.assertRedirects(response, reverse('appointments:list'))
        self.assertEqual(PracticeAvailabilityOverride.objects.filter(practice=practice).count(), 1)
        self.assertEqual(PracticeAvailabilityOverride.objects.filter(practice=other_practice).count(), 0)

    def test_calendar_shows_only_current_practice_and_period_availability_changes(self):
        user, practice, _therapist, _client = self.create_practice_user()
        target_date = timezone.localdate() + timedelta(days=1)
        PracticeAvailabilityOverride.objects.create(
            practice=practice,
            date=target_date,
            starts_at=time(10, 0),
            ends_at=time(14, 0),
            is_available=True,
            note='School holiday hours',
        )
        other_practice = Practice.objects.create(name='Other Practice')
        PracticeAvailabilityOverride.objects.create(practice=other_practice, date=target_date, is_available=False, note='Other clinic hours')
        PracticeAvailabilityOverride.objects.create(practice=practice, date=target_date + timedelta(days=60), is_available=False, note='Later holiday')

        self.client.force_login(user)
        response = self.client.get(reverse('appointments:list'), {'view': 'week', 'date': target_date.isoformat()})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Review availability changes')
        self.assertContains(response, 'School holiday hours')
        self.assertContains(response, 'Remove change')
        self.assertNotContains(response, 'Other clinic hours')
        self.assertNotContains(response, 'Later holiday')

    def test_edit_availability_changes_only_selected_record_and_preserves_calendar_return(self):
        user, practice, _therapist, _client = self.create_practice_user()
        target_date = timezone.localdate() + timedelta(days=1)
        own = PracticeAvailabilityOverride.objects.create(practice=practice, date=target_date, starts_at=time(9), ends_at=time(12))
        second = PracticeAvailabilityOverride.objects.create(practice=practice, date=target_date, starts_at=time(14), ends_at=time(17))
        return_url = reverse('appointments:list') + '?view=week&date=' + target_date.isoformat() + '&q=Maya'
        self.client.force_login(user)
        page = self.client.get(reverse('appointments:availability_edit', args=[own.pk]), {'next': return_url})
        self.assertContains(page, 'Edit this date')
        response = self.client.post(reverse('appointments:availability_edit', args=[own.pk]), {
            'date': (target_date + timedelta(days=5)).isoformat(), 'is_available': 'on',
            'starts_at': '10:00', 'ends_at': '13:00', 'note': 'Adjusted hours', 'next': return_url,
        })
        self.assertRedirects(response, return_url)
        own.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(own.date, target_date)
        self.assertEqual(own.starts_at, time(10))
        self.assertEqual(second.starts_at, time(14))
        self.assertEqual(PracticeAvailabilityOverride.objects.filter(practice=practice).count(), 2)
        event = AuditLog.objects.get(action=AuditLog.Action.UPDATE, object_type='appointments.PracticeAvailabilityOverride')
        self.assertEqual(event.object_id, str(own.pk))
        self.assertNotIn('note', event.metadata)

    def test_availability_edit_rejects_invalid_hours_and_other_practice(self):
        user, practice, _therapist, _client = self.create_practice_user()
        own = PracticeAvailabilityOverride.objects.create(practice=practice, date=timezone.localdate(), starts_at=time(9), ends_at=time(17))
        other_practice = Practice.objects.create(name='Other Practice')
        other = PracticeAvailabilityOverride.objects.create(practice=other_practice, date=timezone.localdate(), is_available=False)
        self.client.force_login(user)
        response = self.client.post(reverse('appointments:availability_edit', args=[own.pk]), {'is_available': 'on', 'starts_at': '17:00', 'ends_at': '09:00'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Availability must end after it starts.')
        own.refresh_from_db()
        self.assertEqual(own.starts_at, time(9))
        self.assertEqual(self.client.get(reverse('appointments:availability_edit', args=[other.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('appointments:availability_edit', args=[other.pk]), {}).status_code, 404)

    def test_availability_edit_supports_full_day_and_rejects_external_return_url(self):
        user, practice, _therapist, _client = self.create_practice_user()
        own = PracticeAvailabilityOverride.objects.create(practice=practice, date=timezone.localdate(), starts_at=time(9), ends_at=time(17))
        self.client.force_login(user)
        response = self.client.post(reverse('appointments:availability_edit', args=[own.pk]), {
            'starts_at': '', 'ends_at': '', 'note': 'Closed', 'next': 'https://example.org/',
        })
        self.assertRedirects(response, reverse('appointments:list'))
        own.refresh_from_db()
        self.assertTrue(own.is_full_day_unavailable)

    def test_read_only_calendar_user_cannot_edit_or_remove_availability(self):
        user, practice, _therapist, _client = self.create_practice_user()
        profile = user.nuvia_profile
        profile.role = UserProfile.Role.THERAPIST
        profile.permissions = {'appointments': {'view': True, 'edit': False, 'delete': False}}
        profile.save()
        own = PracticeAvailabilityOverride.objects.create(practice=practice, date=timezone.localdate(), is_available=False)
        self.client.force_login(user)
        response = self.client.get(reverse('appointments:list'), {'view': 'day', 'date': own.date.isoformat()})
        self.assertContains(response, 'Review availability changes')
        self.assertNotContains(response, reverse('appointments:availability_edit', args=[own.pk]))
        self.assertNotContains(response, reverse('appointments:availability_delete', args=[own.pk]))
        self.assertRedirects(self.client.post(reverse('appointments:availability_edit', args=[own.pk]), {}), reverse('dashboard'))
        self.assertRedirects(self.client.post(reverse('appointments:availability_delete', args=[own.pk]), {}), reverse('dashboard'))
        self.assertTrue(PracticeAvailabilityOverride.objects.filter(pk=own.pk).exists())

    def test_removing_availability_does_not_change_existing_appointment(self):
        user, practice, therapist, client = self.create_practice_user()
        starts = timezone.now() + timedelta(days=1)
        appointment = Appointment.objects.create(practice=practice, therapist=therapist, client=client, starts_at=starts, ends_at=starts + timedelta(minutes=50))
        own = PracticeAvailabilityOverride.objects.create(practice=practice, date=timezone.localdate(starts), is_available=False)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('appointments:availability_delete', args=[own.pk])).status_code, 405)
        response = self.client.post(reverse('appointments:availability_delete', args=[own.pk]))
        self.assertRedirects(response, reverse('appointments:list'))
        appointment.refresh_from_db()
        self.assertEqual(appointment.starts_at, starts)
        self.assertEqual(appointment.status, Appointment.Status.SCHEDULED)

    def test_calendar_availability_delete_is_scoped_to_user_practice(self):
        user, practice, _therapist, _client = self.create_practice_user()
        _other_user, other_practice, _other_therapist, _other_client = self.create_practice_user(
            username='otherdoc',
            practice_name='Other Practice',
        )
        target_date = timezone.localdate() + timedelta(days=1)
        own_override = PracticeAvailabilityOverride.objects.create(
            practice=practice,
            date=target_date,
            starts_at=time(10, 0),
            ends_at=time(14, 0),
            is_available=True,
        )
        other_override = PracticeAvailabilityOverride.objects.create(
            practice=other_practice,
            date=target_date,
            starts_at=time(9, 0),
            ends_at=time(12, 0),
            is_available=True,
        )

        self.client.force_login(user)
        blocked_response = self.client.post(reverse('appointments:availability_delete', args=[other_override.pk]))
        self.assertEqual(blocked_response.status_code, 404)
        self.assertTrue(PracticeAvailabilityOverride.objects.filter(pk=other_override.pk).exists())

        response = self.client.post(reverse('appointments:availability_delete', args=[own_override.pk]))

        self.assertRedirects(response, reverse('appointments:list'))
        self.assertFalse(PracticeAvailabilityOverride.objects.filter(pk=own_override.pk).exists())
        self.assertTrue(practice.audit_logs.filter(action=AuditLog.Action.DELETE, object_type='appointments.PracticeAvailabilityOverride').exists())

    def test_settings_sidebar_does_not_show_availability_link(self):
        user, _practice, _therapist, _client = self.create_practice_user()

        self.client.force_login(user)
        response = self.client.get(reverse('appointments:list'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '>Availability</a>')
        self.assertContains(response, 'Set availability')

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
        self.assertContains(response, 'data-confirm-message="Delete this appointment? Its calendar record will be removed."')

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
