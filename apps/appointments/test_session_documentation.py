from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from apps.accounts.models import UserProfile
from apps.clients.models import Client
from apps.clinical.models import SessionNote
from apps.practices.models import Practice, TherapistProfile
from .models import Appointment


class SessionDocumentationTests(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(name='Fictional session practice')
        self.owner = self.user('owner', 'owner')
        self.therapist_user = self.user('therapist', 'therapist')
        self.other_user = self.user('other', 'therapist')
        self.patient = Client.objects.create(practice=self.practice, first_name='Fictional', last_name='Client')
        self.own = self.appointment(self.therapist_user)
        self.other = self.appointment(self.other_user)

    def user(self, name, role):
        user = get_user_model().objects.create_user(username='sessions-'+name)
        UserProfile.objects.create(user=user, practice=self.practice, role=role)
        TherapistProfile.objects.create(user=user, practice=self.practice, license_number=name, license_state='CA')
        return user

    def appointment(self, user, **changes):
        values = dict(practice=self.practice, client=self.patient, therapist=user.therapist_profile,
                      starts_at=timezone.now()-timedelta(hours=2), ends_at=timezone.now()-timedelta(hours=1), status='completed')
        values.update(changes)
        return Appointment.objects.create(**values)

    def note(self, appointment=None, **changes):
        appointment = appointment or self.own
        values = dict(practice=self.practice, client=self.patient, therapist=appointment.therapist, appointment=appointment,
                      note_type='progress_note', content='Fictional session documentation')
        values.update(changes)
        return SessionNote.objects.create(**values)

    def listing(self, user, **params):
        self.client.force_login(user)
        return self.client.get(reverse('appointments:list'), {'view': 'list', **params})

    def test_therapist_scope_and_direct_url_cannot_be_bypassed(self):
        for view in ['list', 'week']:
            response = self.listing(self.therapist_user, view=view)
            self.assertEqual([a.pk for a in response.context['appointments']], [self.own.pk])
        response = self.listing(self.therapist_user, therapist=str(self.other.therapist_id))
        self.assertEqual(list(response.context['appointments']), [])
        self.assertEqual(self.client.get(reverse('appointments:edit', args=[self.other.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('clinical:create'), {'appointment': self.other.pk}).status_code, 404)
        for role in ['owner', 'admin']:
            self.owner.nuvia_profile.role = role
            self.owner.nuvia_profile.save()
            self.assertEqual(self.listing(self.owner).context['paginator'].count, 2)

    def test_ended_notes_unsigned_locked_and_signed_are_distinct(self):
        response = self.listing(self.therapist_user)
        self.assertTrue(response.context['appointments'][0].documentation_pending)
        self.assertContains(response, 'Note missing')
        note = self.note(is_locked=True)
        response = self.listing(self.therapist_user)
        self.assertContains(response, 'Signature pending')
        self.assertFalse(note.signed_at)
        original_content, locked_at = note.content, note.locked_at
        note = note.sign(self.therapist_user, note.review_digest())
        self.assertEqual(note.content, original_content)
        self.assertEqual(note.locked_at, locked_at)
        self.assertEqual(note.signed_by_id, self.therapist_user.pk)
        response = self.listing(self.therapist_user)
        self.assertFalse(response.context['appointments'][0].documentation_pending)
        self.assertEqual(self.listing(self.therapist_user, documentation='needs_attention').context['paginator'].count, 0)
        with self.assertRaises(ValidationError):
            note.content = 'Changed'
            note.save()
        with self.assertRaises(ValidationError):
            SessionNote.objects.filter(pk=note.pk).update(content='Changed')

    def test_future_cancelled_and_no_show_are_not_documentation_alerts(self):
        self.own.status='cancelled'; self.own.save()
        self.other.status='no_show'; self.other.save()
        self.appointment(self.owner, starts_at=timezone.now()+timedelta(hours=1), ends_at=timezone.now()+timedelta(hours=2), status='scheduled')
        response = self.listing(self.owner)
        self.assertFalse(any(a.documentation_pending for a in response.context['appointments']))

    def test_signing_requires_author_confirmation_and_current_review(self):
        note = self.note()
        url = reverse('clinical:sign', args=[note.pk])
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(url, {'confirm_signature':'on', 'review_digest':note.review_digest()}).status_code, 403)
        self.client.force_login(self.therapist_user)
        self.client.post(url, {'review_digest':note.review_digest()})
        note.refresh_from_db(); self.assertIsNone(note.signed_at)
        digest = note.review_digest()
        note.content='Updated fictional documentation'; note.save()
        self.client.post(url, {'confirm_signature':'on','review_digest':digest})
        note.refresh_from_db(); self.assertIsNone(note.signed_at)
        self.client.post(url, {'confirm_signature':'on','review_digest':note.review_digest()})
        note.refresh_from_db(); self.assertIsNotNone(note.signed_at)
        self.assertContains(self.client.get(url), 'Signed by')
        first_signed_at = note.signed_at
        self.client.post(url, {'confirm_signature':'on','review_digest':note.review_digest()})
        note.refresh_from_db(); self.assertEqual(note.signed_at, first_signed_at)

    def test_blank_note_future_note_and_other_practice_cannot_be_signed(self):
        note = self.note(content='  ')
        with self.assertRaises(ValidationError): note.sign(self.therapist_user, note.review_digest())
        future = self.appointment(self.therapist_user, starts_at=timezone.now()+timedelta(hours=1), ends_at=timezone.now()+timedelta(hours=2))
        note = self.note(future)
        with self.assertRaises(ValidationError): note.sign(self.therapist_user, note.review_digest())
        other_practice = Practice.objects.create(name='Other practice')
        outsider = get_user_model().objects.create_user(username='outsider')
        UserProfile.objects.create(user=outsider, practice=other_practice, role='owner')
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(reverse('clinical:sign', args=[note.pk])).status_code, 404)

    def test_list_paginates_and_filter_links_survive(self):
        for _ in range(25): self.appointment(self.therapist_user)
        response = self.listing(self.therapist_user, documentation='needs_attention', q='Fictional')
        self.assertEqual(len(response.context['appointments']), 25)
        self.assertEqual(response.context['paginator'].count, 26)
        self.assertIn('documentation=needs_attention', response.context['next_list_url'])


    def test_signature_is_exported_and_immutable_in_database(self):
        from django.db import connection, transaction, IntegrityError
        from apps.accounts.export import build_export_data
        note = self.note()
        note = note.sign(self.therapist_user, note.review_digest())
        signature = note.signature
        with self.assertRaises(ValidationError):
            signature.signer_name = 'Other signer'
            signature.save()
        if connection.vendor == 'postgresql':
            for sql in ['UPDATE clinical_sessionnotesignature SET signer_name = %s WHERE id = %s', 'DELETE FROM clinical_sessionnotesignature WHERE signer_name <> %s AND id = %s']:
                with self.assertRaises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
                    cursor.execute(sql, ['forged', signature.pk])
        exported = build_export_data(self.practice, 'clinical')['session_note_signatures']
        self.assertEqual(exported[0]['signed_by_id'], self.therapist_user.pk)
        self.assertEqual(exported[0]['digest'], note.review_digest())


    def test_review_keeps_list_filters_and_rejects_external_return_url(self):
        note = self.note()
        self.client.force_login(self.therapist_user)
        path = reverse('appointments:list') + '?view=list&documentation=needs_attention&page=2'
        response = self.client.get(reverse('clinical:sign', args=[note.pk]), {'next': path})
        self.assertEqual(response.context['next_url'], path)
        for invalid in ['https://example.invalid/', 'http://[', '//example.invalid/appointments/']:
            response = self.client.get(reverse('clinical:sign', args=[note.pk]), {'next': invalid})
            self.assertEqual(response.context['next_url'], reverse('appointments:list')+'?view=list')

    def test_therapist_cannot_assign_a_session_or_note_to_another_author(self):
        from .forms import AppointmentForm
        from apps.clinical.forms import SessionNoteForm
        data = dict(client=self.patient.pk, therapist=self.other.therapist_id,
                    starts_at=(timezone.now()+timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
                    ends_at=(timezone.now()+timedelta(days=1,hours=1)).strftime('%Y-%m-%dT%H:%M'),
                    appointment_type='in_person', status='scheduled')
        form = AppointmentForm(data, practice=self.practice, user=self.therapist_user)
        self.assertFalse(form.is_valid())
        self.assertIn('therapist', form.errors)
        form = SessionNoteForm(dict(client=self.patient.pk, therapist=self.other.therapist_id,
                   appointment=self.other.pk, content='Fictional note', note_type='progress_note'), practice=self.practice, user=self.therapist_user)
        self.assertFalse(form.is_valid())
        self.assertIn('therapist', form.errors)
        self.assertIn('appointment', form.errors)
