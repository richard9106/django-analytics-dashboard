from datetime import timedelta
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, transaction, IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from apps.accounts.models import UserProfile
from apps.accounts.export import build_export_data, build_excel_export
from apps.appointments.models import Appointment
from apps.clients.models import Client
from apps.practices.models import Practice, TherapistProfile
from .models import SessionNote, SessionNoteAddendum


@override_settings(MFA_REQUIRED=False)
class AddendumWorkflowTests(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(name='Fictional practice A')
        self.other = Practice.objects.create(name='Fictional practice B')
        self.user = self.make_user('author', self.practice, 'therapist')
        self.peer = self.make_user('peer', self.practice, 'therapist')
        self.admin = self.make_user('admin', self.practice, 'admin')
        self.outsider = self.make_user('outsider', self.other, 'therapist')
        self.patient = Client.objects.create(practice=self.practice, first_name='Fictional', last_name='Patient')
        appointment = Appointment.objects.create(practice=self.practice, client=self.patient,
            therapist=self.user.therapist_profile, starts_at=timezone.now()-timedelta(hours=2),
            ends_at=timezone.now()-timedelta(hours=1))
        self.note = SessionNote.objects.create(practice=self.practice, client=self.patient,
            therapist=self.user.therapist_profile, appointment=appointment, content='Fictional original clinical note')
        self.note = self.note.sign(self.user, self.note.review_digest())
        self.url = reverse('clinical:addendum', args=[self.note.pk])
        self.client.force_login(self.user)

    def make_user(self, name, practice, role):
        user=get_user_model().objects.create_user(username=name)
        UserProfile.objects.create(user=user, practice=practice, role=role)
        TherapistProfile.objects.create(user=user, practice=practice, license_number=name, license_state='XX')
        return user

    def review(self):
        response=self.client.post(self.url, {'action':'review', 'reason':'Correct a transcription', 'content':'Fictional corrected information'})
        self.assertEqual(response.status_code,200)
        return response.context['review_token']

    def test_review_sign_history_export_and_duplicate_submission(self):
        original=self.note.review_digest()
        token=self.review()
        payload={'action':'sign','review_token':token,'confirm_signature':'on'}
        for _ in range(2):
            self.assertEqual(self.client.post(self.url,payload).status_code,302)
        entry=SessionNoteAddendum.objects.get()
        self.assertEqual(entry.digest,entry.review_digest())
        self.note.refresh_from_db()
        self.assertEqual(original,self.note.review_digest())
        self.assertContains(self.client.get(reverse('clinical:sign',args=[self.note.pk])),entry.content)
        exported=build_export_data(self.practice,'clinical')
        self.assertEqual(exported['session_note_addenda'][0]['content'],entry.content)
        self.assertEqual(build_excel_export(self.practice,'clinical',exported).status_code,200)

    def test_unconfirmed_tampered_and_expired_reviews_cannot_sign(self):
        from unittest.mock import patch
        token=self.review()
        self.client.post(self.url,{'action':'sign','review_token':token})
        self.assertFalse(SessionNoteAddendum.objects.exists())
        self.client.post(self.url,{'action':'sign','review_token':token+'changed','confirm_signature':'on'})
        self.assertFalse(SessionNoteAddendum.objects.exists())
        with patch('django.core.signing.time.time',return_value=timezone.now().timestamp()+1900):
            self.client.post(self.url,{'action':'sign','review_token':token,'confirm_signature':'on'})
        self.assertFalse(SessionNoteAddendum.objects.exists())

    def test_note_and_addendum_permissions_matrix(self):
        for user, review_status, addendum_status in [(self.user,200,200),(self.admin,200,403),(self.peer,404,404),(self.outsider,404,404)]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(reverse('clinical:sign',args=[self.note.pk])).status_code,review_status)
                self.assertEqual(self.client.get(self.url).status_code,addendum_status)
                self.assertEqual(self.client.post(self.url,{'action':'review','reason':'x','content':'x'}).status_code,addendum_status)

    def test_unsigned_note_cannot_receive_addendum(self):
        draft=SessionNote.objects.create(practice=self.practice,client=self.patient,therapist=self.user.therapist_profile,content='draft')
        self.assertEqual(self.client.get(reverse('clinical:addendum',args=[draft.pk])).status_code,403)

    def test_signed_addendum_is_immutable_in_orm_and_sql(self):
        self.client.post(self.url,{'action':'sign','review_token':self.review(),'confirm_signature':'on'})
        entry=SessionNoteAddendum.objects.get()
        for operation in (lambda: entry.save(), lambda: entry.delete(),
                          lambda: SessionNoteAddendum.objects.update(content='changed'), lambda: SessionNoteAddendum.objects.all().delete()):
            with self.assertRaises(ValidationError): operation()
        if connection.vendor=='postgresql':
            for sql in ['UPDATE clinical_sessionnoteaddendum SET content = %s', 'DELETE FROM clinical_sessionnoteaddendum WHERE content = %s']:
                with self.assertRaises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
                    cursor.execute(sql,['changed']) if sql.startswith('UPDATE') else cursor.execute(sql,[entry.content])

    def test_review_token_cannot_be_reused_by_another_author(self):
        token=self.review()
        self.client.force_login(self.peer)
        response=self.client.post(self.url,{'action':'sign','review_token':token,'confirm_signature':'on'})
        self.assertEqual(response.status_code,404)
        self.assertFalse(SessionNoteAddendum.objects.exists())

    def test_document_scope_and_portal_visibility_matrix(self):
        from tempfile import TemporaryDirectory
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.documents.models import ClientDocument
        from apps.portal.models import ClientPortalAccess
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            visible=ClientDocument.objects.create(practice=self.practice,client=self.patient,title='Fictional visible',
                file=SimpleUploadedFile('visible.txt',b'fictional document'),visible_to_client=True)
            hidden=ClientDocument.objects.create(practice=self.practice,client=self.patient,title='Fictional hidden',
                file=SimpleUploadedFile('hidden.txt',b'fictional hidden'),visible_to_client=False)
            patient2=Client.objects.create(practice=self.practice,first_name='Second',last_name='Fictional')
            other=ClientDocument.objects.create(practice=self.practice,client=patient2,title='Second patient',
                file=SimpleUploadedFile('other.txt',b'fictional second document'),visible_to_client=True)
            portal=get_user_model().objects.create_user(username='portal-fictional')
            UserProfile.objects.create(user=portal,practice=self.practice,role='client')
            access=ClientPortalAccess.objects.create(practice=self.practice,client=self.patient,user=portal,is_active=True)
            for user, statuses in [(self.user,[200,200,200]),(self.admin,[200,200,200]),(self.outsider,[404,404,404]),(portal,[200,404,404])]:
                self.client.force_login(user)
                for doc,status in zip([visible,hidden,other],statuses):
                    response=self.client.get(reverse('documents:download',args=[doc.pk]))
                    self.assertEqual(response.status_code,status)
                    if response.streaming: self.assertTrue(b''.join(response.streaming_content))
            self.client.force_login(portal)
            self.assertEqual(self.client.get(reverse('clinical:sign',args=[self.note.pk])).status_code,302)
            self.assertEqual(self.client.post(self.url,{'action':'review','reason':'x','content':'x'}).status_code,302)
            access.is_active=False;access.save()
            self.assertNotEqual(self.client.get(reverse('documents:download',args=[visible.pk])).status_code,200)

    def test_editing_and_expired_review_keep_draft_and_require_new_review(self):
        from unittest.mock import patch
        token=self.review()
        payload={'action':'edit','reason':'Correct wording','content':'Fictional new draft'}
        response=self.client.post(self.url,payload)
        self.assertContains(response,'Fictional new draft')
        self.assertNotContains(response,'name="review_token"')
        with patch('django.core.signing.time.time',return_value=timezone.now().timestamp()+1900):
            response=self.client.post(self.url,dict(payload,action='sign',review_token=token,confirm_signature='on'))
        self.assertContains(response,'Fictional new draft')
        self.assertNotContains(response,'name="review_token"')
        self.assertFalse(SessionNoteAddendum.objects.exists())
