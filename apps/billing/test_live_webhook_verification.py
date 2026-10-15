import hashlib
import hmac
import json
import time
from django.test import TestCase, override_settings
from django.urls import reverse
from apps.audit.models import AuditLog
from apps.practices.models import Practice
from .models import PracticeSubscription

@override_settings(STRIPE_SECRET_KEY='sk_test_fictional',STRIPE_WEBHOOK_SECRET='whsec_sandbox',STRIPE_LIVE_VERIFY_WEBHOOK_SECRET='whsec_live_probe',STRIPE_LIVE_VERIFY_NONCE='fictional-probe')
class LiveWebhookVerificationTests(TestCase):
    def setUp(self):
        p=Practice.objects.create(name='Fictional unaffected practice')
        self.subscription=PracticeSubscription.objects.create(practice=p,plan='solo',billing_period='monthly',status='active',stripe_subscription_id='sub_existing')

    def send(self, secret='whsec_live_probe', **extra):
        obj={'object':'billing_portal.configuration','metadata':{'nuviamy_webhook_verification':'fictional-probe'}}
        event={'id':'evt_probe','livemode':True,'type':'billing_portal.configuration.updated','data':{'object':obj},**extra}
        body=json.dumps(event).encode()
        stamp=str(int(time.time()))
        digest=hmac.new(secret.encode(),stamp.encode()+b'.'+body,hashlib.sha256).hexdigest()
        return self.client.post(reverse('billing:stripe_webhook'),body,content_type='application/json',HTTP_STRIPE_SIGNATURE=f't={stamp},v1={digest}')

    def test_signed_live_probe_is_audited_without_changing_subscription(self):
        self.assertEqual(self.send().status_code,200)
        a=AuditLog.objects.get(object_type='stripe_live_webhook_verification')
        self.assertEqual(a.metadata['stripe_event_id'],'evt_probe')
        self.assertIsNone(a.practice_id)
        self.assertEqual(set(a.metadata),{'stripe_event_id','probe_id','livemode','payload_sha256'})
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status,'active')
        self.assertEqual(PracticeSubscription.objects.count(),1)

    def test_live_financial_events_and_bad_nonce_are_rejected(self):
        for change in ({'type':'customer.subscription.updated'},{'type':'checkout.session.completed'},{'livemode':False},{'data':{'object':{'object':'billing_portal.configuration','metadata':{}}}}):
            self.assertEqual(self.send(**change).status_code,400)
        self.assertFalse(AuditLog.objects.filter(object_type='stripe_live_webhook_verification').exists())
        self.subscription.refresh_from_db();self.assertEqual(self.subscription.status,'active')

    def test_wrong_secret_is_not_accepted(self):
        self.assertEqual(self.send(secret='wrong').status_code,400)
        self.assertFalse(AuditLog.objects.exists())

    def test_sandbox_verifier_still_operates_independently(self):
        self.assertEqual(self.send(secret='whsec_sandbox',livemode=False,type='irrelevant.sandbox.event').status_code,200)
        self.assertFalse(AuditLog.objects.filter(object_type='stripe_live_webhook_verification').exists())

    @override_settings(STRIPE_LIVE_VERIFY_WEBHOOK_SECRET='')
    def test_probe_is_disabled_without_its_secret(self):
        self.assertEqual(self.send().status_code,400)

    @override_settings(STRIPE_LIVE_VERIFY_NONCE='')
    def test_probe_is_disabled_without_nonce(self):
        self.assertEqual(self.send().status_code,400)

    @override_settings(STRIPE_SECRET_KEY='sk_live_fictional')
    def test_secondary_probe_verifier_is_disabled_in_live_payment_mode(self):
        self.assertEqual(self.send().status_code,400)
