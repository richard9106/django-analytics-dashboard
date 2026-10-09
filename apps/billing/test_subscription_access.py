from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.forms import PracticeSignupForm
from apps.accounts.models import UserProfile
from apps.clients.models import Client
from apps.practices.models import Practice
from .access import subscription_access
from .models import PracticeSubscription
from .views import _sync_subscription_from_stripe


class SubscriptionAccessTests(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(name='Subscription test', subscription_required=True)
        self.owner = get_user_model().objects.create_user(username='subscription-owner')
        UserProfile.objects.create(user=self.owner, practice=self.practice, role=UserProfile.Role.OWNER)
        self.patient = Client.objects.create(practice=self.practice, first_name='Fictional', last_name='Patient')
        self.client.force_login(self.owner)

    def subscription(self, status, **kwargs):
        return PracticeSubscription.objects.create(practice=self.practice, plan='solo', billing_period='monthly', status=status, **kwargs)

    def test_abandoned_signup_cannot_access_or_create_records(self):
        self.assertRedirects(self.client.get(reverse('clients:list')), reverse('billing:subscription_access'))
        response = self.client.post(reverse('clients:create'), {'first_name': 'Blocked'}, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Client.objects.filter(practice=self.practice).count(), 1)
        self.assertContains(self.client.get(reverse('billing:subscription_access')), 'Choose a subscription')

    def test_trialing_and_active_allow_workspace(self):
        sub = self.subscription('trialing')
        for status in ('trialing', 'active'):
            sub.status = status
            sub.save()
            self.assertEqual(self.client.get(reverse('clients:list')).status_code, 200)
            self.assertEqual(subscription_access(self.practice)['mode'], 'full')

    def test_grace_expires_after_seven_days(self):
        sub = self.subscription('past_due', payment_failed_at=timezone.now()-timedelta(days=6))
        self.assertEqual(subscription_access(self.practice)['mode'], 'grace')
        self.assertEqual(self.client.get(reverse('clients:create')).status_code, 200)
        sub.payment_failed_at = timezone.now()-timedelta(days=7)
        sub.save()
        self.assertEqual(subscription_access(self.practice)['mode'], 'readonly')
        self.assertRedirects(self.client.get(reverse('clients:create')), reverse('billing:subscription_access'))

    def test_canceled_keeps_records_and_export_but_blocks_writes(self):
        self.subscription('canceled')
        self.assertContains(self.client.get(reverse('clients:list')), 'Fictional')
        self.assertEqual(self.client.post(reverse('practice_data_export')).status_code, 200)
        response = self.client.post(reverse('clients:delete', args=[self.patient.pk]))
        self.assertRedirects(response, reverse('billing:subscription_access'))
        self.assertTrue(Client.objects.filter(pk=self.patient.pk).exists())
        self.assertEqual(self.client.get(reverse('logout')).status_code, 200)
        self.assertRedirects(self.client.get(reverse('practice_settings:google_connect')), reverse('billing:subscription_access'))

    def test_therapist_is_not_offered_checkout(self):
        profile = self.owner.nuvia_profile
        profile.role = UserProfile.Role.THERAPIST
        profile.save()
        response = self.client.get(reverse('billing:subscription_access'))
        self.assertContains(response, 'Ask your practice owner')
        self.assertNotContains(response, 'Start monthly trial')

    def test_public_booking_does_not_accept_requests_without_activation(self):
        self.client.logout()
        url = reverse('public_booking', args=[self.practice.public_booking_slug])
        self.assertContains(self.client.get(url), 'temporarily unavailable', status_code=403)
        self.assertEqual(self.client.post(url, {}).status_code, 403)

    def test_legacy_workspace_is_not_automatically_suspended(self):
        self.practice.subscription_required = False
        self.practice.save()
        self.assertEqual(self.client.get(reverse('clients:list')).status_code, 200)

    @override_settings(STRIPE_PRICE_IDS={'solo': {'monthly': 'price_current'}})
    def test_duplicate_failed_events_do_not_extend_grace_and_recovery_resets_it(self):
        sub = self.subscription('past_due', stripe_subscription_id='sub_current', payment_failed_at=timezone.now()-timedelta(days=5))
        started = sub.payment_failed_at
        payload = {'id': 'sub_current', 'status': 'past_due', 'items': {'data': [{'price': {'id': 'price_current'}}]}}
        _sync_subscription_from_stripe(payload, practice=self.practice)
        sub.refresh_from_db()
        self.assertEqual(sub.payment_failed_at, started)
        _sync_subscription_from_stripe(dict(payload, status='active'), practice=self.practice)
        sub.refresh_from_db()
        self.assertIsNone(sub.payment_failed_at)

    def test_old_subscription_events_cannot_cancel_current_subscription(self):
        sub = self.subscription('active', stripe_subscription_id='sub_current')
        _sync_subscription_from_stripe({'id': 'sub_old', 'status': 'canceled'}, practice=self.practice)
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'active')

    @override_settings(STRIPE_WEBHOOK_SECRET='test-webhook')
    @patch('apps.billing.views.stripe.Webhook.construct_event')
    def test_failed_invoice_supports_new_stripe_shape_without_extending_grace(self, event):
        sub = self.subscription('active', stripe_subscription_id='sub_current')
        event.return_value = {'type':'invoice.payment_failed','data':{'object':{'parent':{'subscription_details':{'subscription':'sub_current'}}}}}
        url = reverse('billing:stripe_webhook')
        self.client.logout()
        self.assertEqual(self.client.post(url, data=b'{}', content_type='application/json').status_code, 200)
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'past_due')
        started = sub.payment_failed_at
        self.client.post(url, data=b'{}', content_type='application/json')
        sub.refresh_from_db()
        self.assertEqual(sub.payment_failed_at, started)
        sub.status='canceled'
        sub.save()
        self.client.post(url, data=b'{}', content_type='application/json')
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'canceled')

    @override_settings(STRIPE_SECRET_KEY='test-placeholder', STRIPE_PRICE_IDS={'solo': {'monthly': 'price_current'}})
    @patch('apps.billing.views.stripe.checkout.Session.retrieve')
    @patch('apps.billing.views.stripe.checkout.Session.create')
    def test_pending_checkout_is_reused_instead_of_creating_duplicate(self, create, retrieve):
        from types import SimpleNamespace
        self.subscription('incomplete', stripe_price_id='price_current', stripe_checkout_session_id='cs_pending')
        retrieve.return_value=SimpleNamespace(status='open',url='https://checkout.stripe.test/pending', metadata={'billing_policy': 'cardless-v1'})
        response=self.client.post(reverse('billing:subscribe',args=['solo','monthly']))
        self.assertEqual(response.url, 'https://checkout.stripe.test/pending')
        create.assert_not_called()

    @override_settings(STRIPE_WEBHOOK_SECRET='test-webhook')
    @patch('apps.billing.views.stripe.Webhook.construct_event')
    @patch('apps.billing.views.stripe.Subscription.retrieve')
    def test_previous_checkout_event_cannot_replace_current_subscription(self, retrieve, event):
        sub=self.subscription('active',stripe_subscription_id='sub_current',stripe_checkout_session_id='cs_current')
        event.return_value={'type':'checkout.session.completed','data':{'object':{'id':'cs_old','subscription':'sub_old','metadata':{'practice_id':str(self.practice.pk)}}}}
        self.client.logout()
        self.client.post(reverse('billing:stripe_webhook'),data=b'{}',content_type='application/json')
        retrieve.assert_not_called()
        sub.refresh_from_db()
        self.assertEqual(sub.stripe_subscription_id,'sub_current')

    @override_settings(STRIPE_SECRET_KEY='test-placeholder', STRIPE_PRICE_IDS={'solo': {'monthly': 'price_current'}})
    @patch('apps.billing.views.stripe.checkout.Session.create')
    def test_active_subscription_cannot_start_duplicate_checkout(self, create):
        self.subscription('active', stripe_subscription_id='sub_current')
        self.assertRedirects(self.client.get(reverse('billing:subscribe', args=['solo','monthly'])), reverse('billing:subscription_access'))
        create.assert_not_called()

    @override_settings(STRIPE_SECRET_KEY='test-placeholder', STRIPE_PRICE_IDS={'solo': {'monthly': 'price_current'}})
    @patch('apps.billing.views.stripe.checkout.Session.create')
    def test_reactivation_does_not_repeat_free_trial(self, create):
        from types import SimpleNamespace
        self.subscription('canceled', stripe_subscription_id='sub_old', stripe_customer_id='cus_test')
        create.return_value = SimpleNamespace(url='https://checkout.stripe.test/session')
        self.client.post(reverse('billing:subscribe', args=['solo','monthly']))
        self.assertNotIn('trial_period_days', create.call_args.kwargs['subscription_data'])

    def test_signup_marks_practice_as_subscription_required(self):
        form = PracticeSignupForm(data={'practice_name':'New practice','practice_type':'solo','first_name':'Test','last_name':'Owner','email':'new-owner@example.invalid','password1':'ValidPasswordForTest2026!','password2':'ValidPasswordForTest2026!','license_number':'test-signup','license_state':'CA'})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save().nuvia_profile.practice.subscription_required)


class CardlessTrialTests(TestCase):
    def signup_data(self, **extra):
        return dict(practice_name='Trial practice', practice_type='solo', first_name='Test', last_name='Owner', email='owner@example.invalid', password1='TrialSecureTest2026!', password2='TrialSecureTest2026!', license_number='trial-unique', license_state='CA', **extra)

    def test_signup_starts_fifteen_days_without_checkout(self):
        form = PracticeSignupForm(self.signup_data())
        self.assertTrue(form.is_valid(), form.errors)
        with patch('stripe.checkout.Session.create') as checkout:
            user = form.save()
        practice = user.nuvia_profile.practice
        self.assertEqual(practice.free_trial_ends_at - practice.free_trial_started_at, timedelta(days=15))
        self.assertEqual(subscription_access(practice)['mode'], 'full')
        checkout.assert_not_called()
        with patch('apps.billing.access.timezone.now', return_value=practice.free_trial_ends_at):
            self.assertEqual(subscription_access(practice)['mode'], 'readonly')
        self.assertFalse(PracticeSubscription.objects.filter(practice=practice).exists())

    def test_private_invitation_is_email_bound_and_single_use(self):
        import hashlib
        from apps.practices.models import EarlyAccessInvitation
        from apps.practices.early_access import assert_free_seat_available
        from django.core.exceptions import ValidationError
        token = 'private-test-token'
        invitation, _ = EarlyAccessInvitation.objects.update_or_create(slot=1, defaults={'email': 'owner@example.invalid', 'token_hash': hashlib.sha256(token.encode()).hexdigest(), 'expires_at': timezone.now()+timedelta(days=30)})
        wrong = self.signup_data(invitation=token)
        wrong['email'] = 'other@example.invalid'
        self.assertFalse(PracticeSignupForm(wrong).is_valid())
        form = PracticeSignupForm(self.signup_data(invitation=token))
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        practice = user.nuvia_profile.practice
        self.assertEqual(practice.free_trial_ends_at.year, practice.free_trial_started_at.year+1)
        self.assertEqual(subscription_access(practice)['free_access'], 'early_access')
        with self.assertRaises(ValidationError):
            assert_free_seat_available(practice)
        invitation.refresh_from_db()
        self.assertEqual(invitation.practice_id, practice.pk)
        from apps.practices.early_access import invitation_for
        with self.assertRaises(ValidationError):
            invitation_for(token, invitation.email)
        PracticeSubscription.objects.create(practice=practice, status='active', stripe_subscription_id='sub_paid')
        assert_free_seat_available(practice)

    def test_pending_checkout_does_not_change_free_deadline(self):
        practice = Practice.objects.create(name='Pending trial', subscription_required=True, free_trial_ends_at=timezone.now()+timedelta(days=1))
        sub = PracticeSubscription.objects.create(practice=practice, status='incomplete')
        self.assertEqual(subscription_access(practice)['mode'], 'full')
        sub.stripe_subscription_id='sub_canceled'
        sub.status='canceled'
        sub.save()
        self.assertEqual(subscription_access(practice)['mode'], 'readonly')


    def test_expired_invitation_and_reissuing_redeemed_slot_are_rejected(self):
        import hashlib
        from django.core.exceptions import ValidationError
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from apps.practices.models import EarlyAccessInvitation
        from apps.practices.early_access import invitation_for
        invitation, _ = EarlyAccessInvitation.objects.update_or_create(slot=2, defaults={'email': 'owner@example.invalid', 'token_hash': hashlib.sha256(b'expired').hexdigest(), 'expires_at': timezone.now()-timedelta(seconds=1)})
        with self.assertRaises(ValidationError):
            invitation_for('expired')
        invitation.redeemed_at = timezone.now()
        invitation.save()
        with self.assertRaises(CommandError):
            call_command('issue_early_access_invitation', 2, invitation.email)
        with self.assertRaises(CommandError):
            call_command('issue_early_access_invitation', 11, invitation.email)
