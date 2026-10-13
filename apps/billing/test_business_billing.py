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
        response=self.client.get(reverse('billing:subscribe',args=['solo','monthly']))
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
        self.client.get(reverse('billing:subscribe',args=['solo','monthly']))
        expire.assert_called_once_with('cs_old')
        self.assertEqual(create.call_args.kwargs['metadata']['billing_policy'],'cardless-v2-billing-info')
