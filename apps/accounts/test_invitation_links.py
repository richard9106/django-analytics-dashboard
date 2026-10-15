import re
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, override_settings, RequestFactory
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from unittest.mock import patch
from apps.practices.models import Practice
from .models import UserProfile
from .invitations import send_account_access_email, invitation_token_generator


@override_settings(MFA_REQUIRED=False)
class InvitationLinkTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='invite', email='invite@example.invalid', password=None)
        self.practice = Practice.objects.create(name='Sensitive practice name')
        UserProfile.objects.create(user=self.user, practice=self.practice, role='admin')
        self.request = RequestFactory().get('/', HTTP_HOST='testserver')

    def send(self):
        send_account_access_email(self.request, self.user)
        self.user.refresh_from_db()
        return re.search(r'https?://\S+', mail.outbox[-1].body).group()

    def complete(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/set-password/', response.url)
        return self.client.post(response.url, {'new_password1':'SafeUnique2026!invite', 'new_password2':'SafeUnique2026!invite'})

    def test_recipient_can_set_password_and_link_is_single_use(self):
        url=self.send()
        self.assertFalse(self.user.has_usable_password())
        self.assertNotIn(self.practice.name, mail.outbox[-1].body)
        self.assertEqual(self.complete(url).status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('SafeUnique2026!invite'))
        self.assertContains(self.client.get(url), 'no longer valid')

    def test_resend_invalidates_prior_link(self):
        old=self.send();new=self.send()
        self.assertNotEqual(old,new)
        self.assertContains(self.client.get(old), 'no longer valid')
        self.assertEqual(self.complete(new).status_code,302)

    def test_invitation_expires_after_48_hours(self):
        url=self.send()
        later=invitation_token_generator._now()+timedelta(hours=49)
        with patch.object(invitation_token_generator,'_now',return_value=later):
            self.assertContains(self.client.get(url),'no longer valid')

    def test_default_recovery_token_does_not_activate_pending_account(self):
        token=default_token_generator.make_token(self.user)
        url=reverse('account_invitation',kwargs={'uidb64':urlsafe_base64_encode(force_bytes(self.user.pk)),'token':token})
        self.assertContains(self.client.get(url),'no longer valid')

    def test_deactivation_and_reactivation_revokes_link(self):
        url=self.send()
        self.user.is_active=False;self.user.save(update_fields=['is_active'])
        self.user.is_active=True;self.user.save(update_fields=['is_active'])
        self.assertContains(self.client.get(url),'no longer valid')

    def test_email_change_revokes_link(self):
        url=self.send()
        self.user.email='changed@example.invalid';self.user.save(update_fields=['email'])
        self.assertContains(self.client.get(url),'no longer valid')

    def test_link_and_form_have_no_store_and_no_referrer(self):
        url=self.send();response=self.client.get(url)
        self.assertEqual(response['Referrer-Policy'],'no-referrer')
        self.assertIn('no-store',response['Cache-Control'])
        response=self.client.get(response.url)
        self.assertEqual(response['Referrer-Policy'],'no-referrer')
        self.assertNotContains(response,url)

    def test_existing_password_is_unchanged_when_reset_email_is_sent(self):
        self.user.set_password('OriginalSecure2026!');self.user.save(update_fields=['password'])
        old=self.user.password
        send_account_access_email(self.request,self.user)
        self.user.refresh_from_db();self.assertEqual(old,self.user.password)
        self.assertIn('/password-reset/',mail.outbox[-1].body)
        self.assertNotIn('OriginalSecure2026!',mail.outbox[-1].body)

    def test_disabled_user_receives_no_link(self):
        self.user.is_active=False;self.user.save(update_fields=['is_active'])
        self.assertFalse(send_account_access_email(self.request,self.user))
        self.assertEqual(len(mail.outbox),0)

    def test_invalid_password_does_not_consume_invitation(self):
        url=self.send();redirect=self.client.get(url)
        response=self.client.post(redirect.url,{'new_password1':'short','new_password2':'short'})
        self.assertEqual(response.status_code,200)
        self.user.refresh_from_db();self.assertFalse(self.user.has_usable_password())
        self.assertEqual(self.complete(url).status_code,302)
