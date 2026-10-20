from apps.accounts.standard_agreements import offer_digest
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from apps.practices.models import Practice
from apps.clients.models import Client
from apps.appointments.models import Appointment
from apps.clinical.models import SessionNote

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', MFA_REQUIRED=False)
class LaunchJourney(TestCase):
    def test_cardless_client_consultation_session_note_signature_expiry(self):
        with patch('stripe.checkout.Session.create') as checkout:
            response=self.client.post(reverse('signup'),dict(accept_terms=True, legal_name='Test legal practice', registered_address='Test street, CA, USA', representative_title='Owner', agreement_digest=offer_digest(), practice_name='Fictional launch acceptance',practice_type='solo',first_name='Fictional',last_name='Therapist',email='journey@example.invalid',password1='FictionalJourney2026!',password2='FictionalJourney2026!',license_number='fictional-launch-13',license_state='CA'))
            self.assertEqual(response.status_code,302)
            checkout.assert_not_called()
        practice=Practice.objects.get(name='Fictional launch acceptance')
        self.assertEqual(practice.free_trial_ends_at-practice.free_trial_started_at,timedelta(days=30))
        therapist=practice.therapists.get()
        self.client.force_login(therapist.user)
        response=self.client.post(reverse('clients:create'),{'first_name':'Fictional','last_name':'Patient','status':'active','primary_therapist':therapist.pk})
        self.assertEqual(response.status_code,302)
        patient=Client.objects.get(practice=practice)
        response=self.client.get(reverse('appointments:create'),{'client':patient.pk,'session_kind':'initial_consultation','date':timezone.localdate().isoformat()})
        self.assertEqual(response.status_code,200)
        initial=response.context['form'].initial
        self.assertEqual(initial['ends_at']-initial['starts_at'],timedelta(minutes=15))
        start=timezone.localtime().replace(hour=10,minute=0,second=0,microsecond=0)-timedelta(days=1)
        for kind,duration in [('initial_consultation',15),('standard',50)]:
            response=self.client.post(reverse('appointments:create'),{'client':patient.pk,'therapist':therapist.pk,'starts_at':start.strftime('%Y-%m-%dT%H:%M'),'ends_at':(start+timedelta(minutes=duration)).strftime('%Y-%m-%dT%H:%M'),'session_kind':kind,'appointment_type':'video','status':'completed','location':'','meeting_url':'','notes':''})
            self.assertEqual(response.status_code,302)
            start+=timedelta(hours=1)
        session=Appointment.objects.get(practice=practice,session_kind='standard')
        response=self.client.post(reverse('clinical:create')+'?appointment='+str(session.pk),{'note_type':'progress_note','content':'Fictional launch acceptance note','treatment_progress':'Fictional progress','is_locked':''})
        self.assertEqual(response.status_code,302)
        note=SessionNote.objects.get(appointment=session)
        response=self.client.post(reverse('clinical:sign',args=[note.pk]),{'confirm_signature':'on','review_digest':note.review_digest()})
        self.assertEqual(response.status_code,302)
        note.refresh_from_db()
        self.assertIsNotNone(note.signed_at)
        self.assertTrue(note.is_locked)
        response=self.client.post(reverse('clinical:addendum',args=[note.pk]),{'action':'review','reason':'Clarify wording','content':'Fictional signed clarification'})
        self.assertEqual(response.status_code,200)
        token=response.context['review_token']
        response=self.client.post(reverse('clinical:addendum',args=[note.pk]),{'action':'sign','review_token':token,'confirm_signature':'on'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(note.addenda.count(),1)
        from apps.accounts.export import build_export_data
        self.assertEqual(len(build_export_data(practice,'clinical')['session_note_addenda']),1)
        with patch('apps.billing.access.timezone.now',return_value=practice.free_trial_ends_at+timedelta(seconds=1)):
            self.client.logout()
            self.client.force_login(therapist.user)
            self.assertEqual(self.client.get(reverse('clients:list')).status_code,200)
            response=self.client.post(reverse('clients:create'),{'first_name':'Blocked','last_name':'Fictional','status':'active'})
            self.assertIn(response.status_code,(302,403))
            self.assertEqual(Client.objects.filter(practice=practice).count(),1)
            self.assertEqual(self.client.post(reverse('practice_data_export')).status_code,200)
