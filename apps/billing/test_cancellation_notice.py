import hashlib
import hmac
import json
import time
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from apps.accounts.models import UserProfile
from apps.practices.models import Practice
from .models import PracticeSubscription
from .access import subscription_access

@override_settings(MFA_REQUIRED=False,STRIPE_SECRET_KEY='',STRIPE_WEBHOOK_SECRET='whsec_fictional_cancellation_test',STRIPE_PRICE_IDS={'solo':{'monthly':'price_fictional'}})
class CancellationNoticeTests(TestCase):
    def setUp(self):
        self.practice=Practice.objects.create(name='Fictional cancellation',subscription_required=True)
        self.user=get_user_model().objects.create_user(username='fictional-cancel')
        UserProfile.objects.create(user=self.user,practice=self.practice,role='owner')
        self.sub=PracticeSubscription.objects.create(practice=self.practice,plan='solo',billing_period='monthly',status='active',stripe_subscription_id='sub_fictional')
        self.until=timezone.now().replace(microsecond=0)+timedelta(days=20)

    def event(self,**extra):
        payload={'id':'sub_fictional','object':'subscription','status':'active','items':{'data':[{'price':{'id':'price_fictional'},'current_period_end':int(self.until.timestamp())}]},'metadata':{'practice_id':str(self.practice.pk)},**extra}
        kind='customer.subscription.deleted' if payload['status']=='canceled' else 'customer.subscription.updated'
        body=json.dumps({'id':'evt_fictional','object':'event','type':kind,'data':{'object':payload}}).encode()
        timestamp=str(int(time.time()))
        digest=hmac.new(b'whsec_fictional_cancellation_test',timestamp.encode()+b'.'+body,hashlib.sha256).hexdigest()
        response=self.client.post(reverse('billing:stripe_webhook'),body,content_type='application/json',HTTP_STRIPE_SIGNATURE=f't={timestamp},v1={digest}')
        self.assertEqual(response.status_code,200)
        self.sub.refresh_from_db()

    def profile(self):
        self.client.force_login(self.user)
        return self.client.get(reverse('profile_settings'))

    def test_explicit_cancel_date_without_period_flag_is_visible(self):
        self.event(cancel_at=int(self.until.timestamp()),cancel_at_period_end=False)
        self.assertTrue(self.sub.cancellation_scheduled)
        self.assertEqual(self.sub.cancellation_effective_at,self.until)
        self.assertEqual(subscription_access(self.practice)['mode'],'full')
        response=self.profile()
        self.assertContains(response,'Cancellation scheduled')
        self.assertContains(response,'will not renew.')
        self.assertContains(response,'including the full day (UTC).')

    def test_period_end_flag_uses_item_period_end(self):
        self.event(cancel_at_period_end=True)
        self.assertEqual(self.sub.cancellation_effective_at,self.until)
        self.assertContains(self.profile(),'Cancellation scheduled')

    def test_removing_scheduled_cancellation_clears_notice(self):
        self.event(cancel_at=int(self.until.timestamp()))
        self.event(cancel_at=None,cancel_at_period_end=False)
        self.assertFalse(self.sub.cancellation_scheduled)
        response=self.profile()
        self.assertNotContains(response,'Cancellation scheduled')
        self.assertContains(response,'Renews on')

    def test_ended_subscription_shows_readonly_and_actual_end(self):
        self.event(status='canceled',cancel_at_period_end=True,ended_at=int(timezone.now().timestamp()))
        self.assertFalse(self.sub.cancellation_scheduled)
        self.assertEqual(subscription_access(self.practice)['mode'],'readonly')
        response=self.profile()
        self.assertContains(response,'Your paid subscription has ended.')
        self.assertContains(response,'Ended ')
        self.assertNotContains(response,'Your access remains active until then.')

    def test_pending_date_never_invents_a_timestamp(self):
        self.sub.cancel_at_period_end=True; self.sub.current_period_end=None; self.sub.save()
        self.assertContains(self.profile(),'Check Stripe for the confirmed end date.')

    def test_overdue_cancellation_does_not_promise_full_access(self):
        self.event(status='past_due',cancel_at=int(self.until.timestamp()))
        self.sub.payment_failed_at=timezone.now()-timedelta(days=8); self.sub.save()
        response=self.profile()
        self.assertContains(response,'Your current access is read-only')
        self.assertNotContains(response,'Your access remains active until then.')

    def test_bad_signature_does_not_modify_cancellation(self):
        response=self.client.post(reverse('billing:stripe_webhook'),b'{}',content_type='application/json',HTTP_STRIPE_SIGNATURE='invalid')
        self.assertEqual(response.status_code,400)
        self.sub.refresh_from_db(); self.assertFalse(self.sub.cancellation_scheduled)

    def test_full_day_access_after_stripe_cancellation_expires_at_midnight(self):
        self.event(cancel_at=int(self.until.timestamp()))
        expected=self.until.replace(hour=0,minute=0,second=0)+timedelta(days=1)
        self.assertEqual(self.sub.cancellation_access_until,expected)
        self.event(status='canceled',ended_at=int(self.until.timestamp()))
        with patch('apps.billing.access.timezone.now',return_value=expected-timedelta(microseconds=1)):
            state=subscription_access(self.practice)
            self.assertEqual(state['mode'],'full')
            self.assertTrue(state['cancellation_extension'])
        with patch('apps.billing.access.timezone.now',return_value=expected):
            self.assertEqual(subscription_access(self.practice)['mode'],'readonly')

    def test_immediate_cancellation_caps_extension_to_actual_end_day(self):
        self.event(cancel_at=int(self.until.timestamp()))
        ended=timezone.now().replace(microsecond=0)
        self.event(status='canceled',ended_at=int(ended.timestamp()))
        self.assertEqual(self.sub.cancellation_access_until,ended.replace(hour=0,minute=0,second=0)+timedelta(days=1))
        response=self.profile()
        self.assertContains(response,'Complimentary access continues through')
        self.assertNotContains(response,'current access is read-only')

    def test_payment_failure_does_not_receive_cancellation_extension(self):
        self.event(cancel_at=int(self.until.timestamp()))
        self.event(status='past_due',cancel_at=int(self.until.timestamp()))
        self.assertIsNone(self.sub.cancellation_access_until)
        self.event(status='canceled',ended_at=int(timezone.now().timestamp()))
        self.assertIsNone(self.sub.cancellation_access_until)
        self.assertEqual(subscription_access(self.practice)['mode'],'readonly')

    def test_dashboard_notice_is_for_subscription_managers(self):
        self.event(cancel_at=int(self.until.timestamp()))
        self.client.force_login(self.user)
        response=self.client.get(reverse('dashboard'))
        self.assertContains(response,'aria-label="Subscription cancellation"',count=1)
        self.assertContains(response,'Manage subscription')
        profile=self.user.nuvia_profile; profile.role='therapist';profile.save()
        self.assertNotContains(self.client.get(reverse('dashboard')),'aria-label="Subscription cancellation"')
