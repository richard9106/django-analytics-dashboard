from .billing_test_data import PROFESSIONAL_BILLING_DATA
from types import SimpleNamespace
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase,override_settings
from django.urls import reverse
from apps.practices.models import Practice
from apps.accounts.models import UserProfile
from .models import PracticeSubscription

@override_settings(MFA_REQUIRED=False,STRIPE_SECRET_KEY='sk_test_fictional',STRIPE_PRICE_IDS={'solo':{'monthly':'price_fictional'}})
class BusinessBillingTests(TestCase):
    def setUp(self):
        self.practice=Practice.objects.create(name='Fictional billing')
        user=get_user_model().objects.create_user(username='fictional-billing')
        UserProfile.objects.create(user=user,practice=self.practice,role='owner')
        self.client.force_login(user)

    @patch('apps.billing.views.stripe.checkout.Session.create')
    def test_existing_customer_saves_billing_name_and_address(self,create):
        PracticeSubscription.objects.create(practice=self.practice,plan='solo',billing_period='monthly',status='canceled',stripe_customer_id='cus_fictional',stripe_subscription_id='sub_old')
        create.return_value=SimpleNamespace(url='https://checkout.stripe.test/fake',id='cs_fictional')
        response=self.client.post(reverse('billing:subscribe',args=['solo','monthly']), PROFESSIONAL_BILLING_DATA)
        self.assertEqual(response.status_code,302)
        self.assertEqual(create.call_args.kwargs['customer_update'],{'name':'auto','address':'auto'})
        self.assertEqual(create.call_args.kwargs['billing_address_collection'],'required')
        self.assertNotIn('automatic_tax',create.call_args.kwargs)

    @patch('apps.billing.views.stripe.checkout.Session.create')
    @patch('apps.billing.views.stripe.checkout.Session.expire')
    @patch('apps.billing.views.stripe.checkout.Session.retrieve')
    def test_legacy_pending_checkout_is_replaced_with_billing_collection(self,retrieve,expire,create):
        PracticeSubscription.objects.create(practice=self.practice,plan='solo',billing_period='monthly',status='incomplete',stripe_price_id='price_fictional',stripe_checkout_session_id='cs_old')
        retrieve.return_value=SimpleNamespace(id='cs_old',status='open',url='https://checkout.stripe.test/old',metadata={'billing_policy':'cardless-v1','active_user_count':'1'})
        create.return_value=SimpleNamespace(id='cs_new',url='https://checkout.stripe.test/new')
        self.client.post(reverse('billing:subscribe',args=['solo','monthly']), PROFESSIONAL_BILLING_DATA)
        expire.assert_called_once_with('cs_old')
        self.assertEqual(create.call_args.kwargs['metadata']['billing_policy'],'cardless-v2-billing-info')

    @override_settings(STRIPE_INVOICE_TEMPLATE_ID='inrtem_fictional')
    @patch('apps.billing.views.stripe.checkout.Session.create')
    @patch('apps.billing.views.stripe.Customer.create')
    def test_new_customer_has_template_before_checkout(self, customer_create, checkout_create):
        customer_create.return_value = SimpleNamespace(id='cus_template')
        checkout_create.return_value = SimpleNamespace(id='cs_template', url='https://checkout.stripe.test/template')
        self.client.post(reverse('billing:subscribe', args=['solo', 'monthly']), PROFESSIONAL_BILLING_DATA)
        self.assertEqual(customer_create.call_args.kwargs['invoice_settings'], {'rendering_options': {'template': 'inrtem_fictional'}})
        self.assertEqual(checkout_create.call_args.kwargs['customer'], 'cus_template')
        self.assertEqual(PracticeSubscription.objects.get(practice=self.practice).stripe_customer_id, 'cus_template')

    @override_settings(STRIPE_INVOICE_TEMPLATE_ID='inrtem_fictional')
    @patch('apps.billing.views.stripe.checkout.Session.create')
    @patch('apps.billing.views.stripe.Customer.modify')
    def test_existing_customer_gets_template(self, modify, checkout_create):
        PracticeSubscription.objects.create(practice=self.practice, status='canceled', stripe_customer_id='cus_existing')
        checkout_create.return_value = SimpleNamespace(id='cs_template', url='https://checkout.stripe.test/template')
        self.client.post(reverse('billing:subscribe', args=['solo', 'monthly']), PROFESSIONAL_BILLING_DATA)
        self.assertEqual(modify.call_args.args, ('cus_existing',))
        self.assertEqual(modify.call_args.kwargs['invoice_settings'], {'rendering_options': {'template': 'inrtem_fictional'}})
        self.assertEqual(modify.call_args.kwargs['address']['country'], 'US')

    @override_settings(STRIPE_INVOICE_TEMPLATE_ID='inrtem_fictional')
    @patch('apps.billing.views.stripe.checkout.Session.create')
    @patch('apps.billing.views.stripe.Customer.modify')
    def test_template_error_blocks_checkout(self, modify, checkout_create):
        import stripe
        PracticeSubscription.objects.create(practice=self.practice, status='canceled', stripe_customer_id='cus_existing')
        modify.side_effect = stripe.error.InvalidRequestError('Invalid template', 'invoice_settings')
        self.client.post(reverse('billing:subscribe', args=['solo', 'monthly']), PROFESSIONAL_BILLING_DATA)
        checkout_create.assert_not_called()

    @patch('apps.billing.views.stripe.checkout.Session.create')
    def test_get_shows_unchecked_declaration_without_checkout(self, checkout_create):
        response = self.client.get(reverse('billing:subscribe', args=['solo','monthly']))
        self.assertContains(response, 'Legal billing name')
        self.assertNotContains(response, 'checked')
        checkout_create.assert_not_called()

    @patch('apps.billing.views.stripe.checkout.Session.create')
    def test_invalid_address_or_missing_declaration_blocks_checkout(self, checkout_create):
        for changes in ({'country':'ZZ'}, {'professional_purchase':''}, {'state':'XX'}, {'postal_code':'bad'}):
            with self.subTest(changes=changes):
                response = self.client.post(reverse('billing:subscribe', args=['solo','monthly']), {**PROFESSIONAL_BILLING_DATA, **changes})
                self.assertContains(response, 'Please check the fields below')
        checkout_create.assert_not_called()

    @patch('apps.billing.views.stripe.checkout.Session.create')
    def test_professional_declaration_is_audited(self, checkout_create):
        from apps.audit.models import AuditLog
        checkout_create.return_value = SimpleNamespace(id='cs_audit', url='https://checkout.stripe.test/audit')
        self.client.post(reverse('billing:subscribe', args=['solo','monthly']), PROFESSIONAL_BILLING_DATA)
        event = AuditLog.objects.get(object_type='subscription_billing_declaration')
        self.assertEqual(event.practice, self.practice)
        self.assertEqual(event.metadata['billing_details']['country'], 'US')
        self.assertTrue(event.metadata['billing_details']['professional_purchase'])

    @patch('apps.billing.views.stripe.checkout.Session.create')
    def test_international_professional_can_continue_to_checkout(self, checkout_create):
        checkout_create.return_value = SimpleNamespace(id='cs_spain', url='https://checkout.stripe.test/spain')
        response = self.client.post(reverse('billing:subscribe', args=['solo','monthly']), {**PROFESSIONAL_BILLING_DATA, 'country':'ES','state':'Zaragoza','postal_code':'50019'})
        self.assertEqual(response.status_code,302)
        checkout_create.assert_called_once()

    def test_international_postal_codes_and_missing_regions_are_allowed(self):
        from .forms import ProfessionalBillingForm
        for country, postal in [('GB','SW1A 1AA'), ('IE',''), ('ES','50019')]:
            form = ProfessionalBillingForm({**PROFESSIONAL_BILLING_DATA,'country':country,'state':'','postal_code':postal})
            self.assertTrue(form.is_valid(),form.errors)
        form = ProfessionalBillingForm({**PROFESSIONAL_BILLING_DATA,'country':'US','state':'New York'})
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(form.cleaned_data['state'],'NY')

    @override_settings(STRIPE_WEBHOOK_SECRET='whsec_international_test')
    @patch('apps.billing.views.stripe.Subscription.retrieve')
    def test_paid_checkout_with_final_non_us_address_still_activates(self, retrieve):
        import hashlib
        import hmac
        import json
        import time
        from .access import subscription_access
        self.practice.subscription_required = True
        self.practice.save(update_fields=['subscription_required'])
        PracticeSubscription.objects.create(practice=self.practice,plan='solo',billing_period='monthly',stripe_checkout_session_id='cs_international')
        retrieve.return_value = {'id':'sub_international','customer':'cus_international','status':'active','metadata':{'practice_id':str(self.practice.pk)},'items':{'data':[{'price':{'id':'price_fictional'}}]}}
        event = {'type':'checkout.session.completed','data':{'object':{'id':'cs_international','subscription':'sub_international','payment_status':'paid','metadata':{'practice_id':str(self.practice.pk)},'customer_details':{'address':{'country':'ES'}}}}}
        body = json.dumps(event).encode()
        timestamp = str(int(time.time()))
        digest = hmac.new(b'whsec_international_test',timestamp.encode()+b'.'+body,hashlib.sha256).hexdigest()
        response = self.client.post(reverse('billing:stripe_webhook'),body,content_type='application/json',HTTP_STRIPE_SIGNATURE=f't={timestamp},v1={digest}')
        self.assertEqual(response.status_code,200)
        self.assertEqual(subscription_access(Practice.objects.get(pk=self.practice.pk))['mode'],'full')

    @patch('apps.billing.views.stripe.checkout.Session.create')
    def test_missing_acceptance_and_old_terms_version_cannot_start_checkout(self, create):
        from apps.audit.models import AuditLog
        for changes in ({'accept_billing_terms':''}, {'billing_terms_version':'outdated'}, {'billing_terms_version':''}):
            with self.subTest(changes=changes):
                response=self.client.post(reverse('billing:subscribe',args=['solo','monthly']), {**PROFESSIONAL_BILLING_DATA,**changes})
                self.assertEqual(response.status_code,200)
                if changes.get('billing_terms_version') == 'outdated':
                    self.assertFalse(response.context['form']['accept_billing_terms'].value())
        create.assert_not_called()
        self.assertFalse(AuditLog.objects.filter(object_type='service_agreement').exists())

    @patch('apps.billing.views.stripe.checkout.Session.create')
    def test_acceptance_records_version_actor_and_checkout_metadata(self, create):
        from apps.accounts.legal import BILLING_TERMS_VERSION
        from apps.audit.models import AuditLog
        create.return_value=SimpleNamespace(id='cs_terms',url='https://checkout.stripe.test/terms')
        self.client.post(reverse('billing:subscribe',args=['solo','monthly']),PROFESSIONAL_BILLING_DATA)
        agreement=AuditLog.objects.get(object_type='service_agreement')
        self.assertEqual(agreement.metadata['event'],'subscription_terms_accepted')
        self.assertEqual(agreement.metadata['billing_terms_version'],BILLING_TERMS_VERSION)
        self.assertTrue(agreement.metadata['test_mode'])
        self.assertEqual(agreement.actor_id_snapshot,self.practice.user_profiles.get().user_id)
        self.assertEqual(create.call_args.kwargs['metadata']['billing_terms_version'],BILLING_TERMS_VERSION)
        response=self.client.get(reverse('billing:subscribe',args=['solo','monthly']))
        self.assertNotContains(response,' checked')
        self.assertContains(response,'#subscription-conditions')

    @patch('apps.billing.views.stripe.checkout.Session.create')
    @patch('apps.billing.views.stripe.checkout.Session.expire')
    @patch('apps.billing.views.stripe.checkout.Session.retrieve')
    def test_pending_checkout_from_previous_terms_is_replaced(self, retrieve, expire, create):
        PracticeSubscription.objects.create(practice=self.practice,status='incomplete',stripe_price_id='price_fictional',stripe_checkout_session_id='cs_old_terms')
        retrieve.return_value=SimpleNamespace(id='cs_old_terms',status='open',metadata={'billing_policy':'cardless-v2-billing-info','active_user_count':'1','billing_terms_version':'old'})
        create.return_value=SimpleNamespace(id='cs_new_terms',url='https://checkout.stripe.test/new')
        self.client.post(reverse('billing:subscribe',args=['solo','monthly']),PROFESSIONAL_BILLING_DATA)
        expire.assert_called_once_with('cs_old_terms')
        create.assert_called_once()
