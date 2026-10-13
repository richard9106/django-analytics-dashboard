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
    def test_invalid_country_or_missing_declaration_blocks_checkout(self, checkout_create):
        for changes in ({'country':'ES'}, {'professional_purchase':''}, {'state':'XX'}, {'postal_code':'bad'}):
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
