from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.appointments.models import Appointment
from apps.clinical.models import TreatmentPlan
from apps.clients.models import Client
from apps.portal.models import ClientPortalAccess
from apps.practices.models import Practice, TherapistProfile
from apps.dashboard.models import Task


@override_settings(MFA_REQUIRED=False)
class DashboardTests(TestCase):
    def setUp(self):
        cache.clear()

    def create_practice_user(self, username='laura', practice_name='Nuvia Therapy'):
        user = get_user_model().objects.create_user(
            username=username,
            email=f'{username}@example.com',
            password='StrongPass123!',
            first_name='Laura',
            last_name='Chen',
        )
        practice = Practice.objects.create(name=practice_name)
        therapist = TherapistProfile.objects.create(
            user=user,
            practice=practice,
            license_number=f'{username}-12345',
            license_state='CA',
        )
        UserProfile.objects.create(
            user=user,
            practice=practice,
            role=UserProfile.Role.OWNER,
        )
        return user, practice, therapist

    def test_dashboard_task_links_count_and_detail_are_scoped(self):
        user, practice, _ = self.create_practice_user()
        Task.objects.bulk_create([Task(practice=practice, title=f'Follow-up {index}', assignee=user, created_by=user) for index in range(55)])
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['task_count'], 55)
        self.assertEqual(response.context['tasks_shown'], 50)
        self.assertContains(response, 'Showing 50 of 55')
        self.assertContains(response, 'aria-labelledby="dashboard-tasks-title" tabindex="0"')
        item = response.context['tasks'][0]
        self.assertEqual(item['href'], reverse('tasks_detail', args=[item['manual'].pk]))
        detail = self.client.get(item['href'])
        self.assertContains(detail, item['manual'].title)
        self.assertContains(detail, 'Mark complete')
        response = self.client.post(reverse('tasks_status', args=[item['manual'].pk]), {'status': 'done', 'next': 'task_detail'})
        self.assertEqual(response.url, item['href'])
        other, _, _ = self.create_practice_user(username='other-tasks')
        self.client.force_login(other)
        self.assertEqual(self.client.get(item['href']).status_code, 404)

    def test_dashboard_billing_remaining_balance_excludes_drafts_and_partial_payments(self):
        from decimal import Decimal
        from apps.billing.models import Invoice, Payment
        user, practice, _ = self.create_practice_user()
        client = Client.objects.create(practice=practice, first_name='Billing', last_name='Client')
        today = timezone.localdate()
        invoice = Invoice.objects.create(practice=practice, client=client, invoice_number='DASH-1', amount='100', status='sent', due_date=today - timedelta(days=1))
        Payment.objects.create(practice=practice, client=client, invoice=invoice, amount='20', paid_at=timezone.now())
        Payment.objects.create(practice=practice, client=client, invoice=invoice, amount='10', paid_at=timezone.now())
        settled = Invoice.objects.create(practice=practice, client=client, invoice_number='SETTLED', amount='50', status='overdue')
        Payment.objects.create(practice=practice, client=client, invoice=settled, amount='50', paid_at=timezone.now())
        Invoice.objects.create(practice=practice, client=client, invoice_number='DRAFT', amount='900', status='draft')
        Invoice.objects.create(practice=practice, client=client, invoice_number='VOID', amount='800', status='void')
        Invoice.objects.create(practice=practice, client=client, invoice_number='PAID', amount='200', status='paid', paid_at=timezone.now())
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['outstanding_balance'], Decimal('70'))
        self.assertEqual(response.context['overdue_invoice_count'], 1)
        self.assertEqual(response.context['open_invoice_count'], 1)
        self.assertEqual(response.context['monthly_revenue'], Decimal('200'))
        html = response.content.decode()
        self.assertLess(html.index('id="dashboard-billing-title"'), html.index('Revenue trend'))

    def test_dashboard_hides_billing_data_and_alerts_without_permission(self):
        from apps.billing.models import Invoice
        user, practice, _ = self.create_practice_user()
        client = Client.objects.create(practice=practice, first_name='Hidden', last_name='Billing')
        Invoice.objects.create(practice=practice, client=client, invoice_number='HIDDEN-INVOICE', amount='123', status='sent')
        profile = user.nuvia_profile
        profile.role = UserProfile.Role.THERAPIST
        profile.permissions = {'tasks': {'view': True}, 'appointments': {'view': True}}
        profile.save()
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, 'HIDDEN-INVOICE')
        self.assertNotContains(response, 'Monthly revenue')
        self.assertNotContains(response, 'Billing follow-up')
        self.assertNotContains(response, 'id="dashboard-billing-title"')
        self.assertEqual(response.context['outstanding_balance'], 0)

    def test_performance_months_use_two_grouped_queries(self):
        from types import SimpleNamespace
        from apps.dashboard.views import DashboardView
        user, practice, _ = self.create_practice_user()
        view = DashboardView()
        view.request = SimpleNamespace(user=user)
        view.can_view('billing')
        with self.assertNumQueries(2):
            months = view.get_performance_months(practice, timezone.localdate())
        self.assertEqual(len(months), 6)
        self.assertTrue(all(month['revenue_height'] == 0 for month in months))

    def test_first_steps_show_only_missing_actions_at_top_and_disappear_when_complete(self):
        from datetime import time
        from apps.appointments.models import PracticeWorkingHour
        user, practice, therapist = self.create_practice_user()
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(len(response.context['dashboard_onboarding_steps']), 3)
        html = response.content.decode()
        self.assertLess(html.index('aria-label="Recommended first steps"'), html.index('aria-label="Workspace actions"'))
        client = Client.objects.create(practice=practice, first_name='First', last_name='Client')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(len(response.context['dashboard_onboarding_steps']), 2)
        self.assertNotIn('Add your first client', [step['label'] for step in response.context['dashboard_onboarding_steps']])
        PracticeWorkingHour.objects.create(practice=practice, weekday=0, starts_at=time(9), ends_at=time(17), active=False)
        starts = timezone.now()
        Appointment.objects.create(practice=practice, client=client, therapist=therapist, starts_at=starts,
                                   ends_at=starts + timedelta(minutes=50), status='cancelled')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['dashboard_onboarding_steps'], [])
        self.assertNotContains(response, 'aria-label="Recommended first steps"')

    def test_first_steps_do_not_offer_actions_without_permission(self):
        user, _, _ = self.create_practice_user()
        profile = user.nuvia_profile
        profile.role = UserProfile.Role.THERAPIST
        profile.permissions = {'tasks': {'view': True}}
        profile.save()
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['dashboard_onboarding_steps'], [])
        self.assertEqual(response.context['session_status_total'], 0)
        self.assertEqual(response.context['invoice_status_total'], 0)

    def test_status_charts_use_real_scoped_recent_data_and_line_geometry(self):
        from apps.billing.models import Invoice
        user, practice, therapist = self.create_practice_user()
        client = Client.objects.create(practice=practice, first_name='Chart', last_name='Client')
        starts = timezone.now()
        for index, status in enumerate(['completed', 'cancelled']):
            Appointment.objects.create(practice=practice, client=client, therapist=therapist,
                starts_at=starts + timedelta(hours=index), ends_at=starts + timedelta(hours=index, minutes=50), status=status)
        Appointment.objects.create(practice=practice, client=client, therapist=therapist,
            starts_at=starts - timedelta(days=400), ends_at=starts - timedelta(days=400) + timedelta(minutes=50))
        Invoice.objects.create(practice=practice, client=client, invoice_number='CHART-PAID', amount='123.45', status='paid', paid_at=starts)
        Invoice.objects.create(practice=practice, client=client, invoice_number='CHART-SENT', amount='100', status='sent')
        other_user, other_practice, other_therapist = self.create_practice_user(username='other-charts')
        other_client = Client.objects.create(practice=other_practice, first_name='Other', last_name='Chart')
        Appointment.objects.create(practice=other_practice, client=other_client, therapist=other_therapist,
            starts_at=starts, ends_at=starts + timedelta(minutes=50))
        Invoice.objects.create(practice=other_practice, client=other_client, invoice_number='OTHER', amount='999', status='paid', paid_at=starts)
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['session_status_total'], 2)
        segments = response.context['session_status_segments']
        self.assertEqual(sum(item['count'] for item in segments), 2)
        self.assertAlmostEqual(sum(float(item['share']) for item in segments), 100, places=2)
        self.assertEqual(response.context['invoice_status_total'], 2)
        self.assertEqual(len(response.context['revenue_chart_points'].split()), 6)
        self.assertTrue(response.context['revenue_chart_has_data'])
        self.assertTrue(response.context['revenue_chart_points'].split()[-1].startswith('504.0,'))
        self.assertTrue(all(16 <= float(point.split(',')[1]) <= 148 for point in response.context['revenue_chart_points'].split()))

    def test_empty_charts_have_no_fabricated_segments_or_values(self):
        user, _, _ = self.create_practice_user()
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertFalse(response.context['revenue_chart_has_data'])
        self.assertEqual(response.context['session_status_segments'], [])
        self.assertEqual(response.context['session_status_total'], 0)
        self.assertEqual(response.context['invoice_status_total'], 0)
        self.assertTrue(all(item['width'] == '0' for item in response.context['invoice_status_breakdown']))

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_home_page_is_public_and_seo_optimized(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Therapy Practice Management Software')
        self.assertContains(response, 'therapy practice management software')
        self.assertContains(response, 'application/ld+json')
        self.assertContains(response, 'https://nuviamy.com/')
        self.assertContains(response, '/static/favicon.svg')
        self.assertContains(response, 'Back to top')
        self.assertContains(response, '>Home</a>')
        self.assertContains(response, reverse('pricing'))
        self.assertContains(response, reverse('features'))
        self.assertContains(response, 'marketing-nav-toggle')
        self.assertContains(response, 'marketing-menu-button')
        self.assertContains(response, '/static/marketing/therapy-practice-hero-banner.webp')
        self.assertContains(response, '/static/marketing/therapist-client-session.webp')
        self.assertContains(response, '/static/marketing/mental-health-clinic-team.webp')
        self.assertContains(response, '/static/marketing/therapy-office-workflow.webp')

    def test_home_page_shows_sign_in_for_visitors_and_dashboard_for_users(self):
        visitor_response = self.client.get(reverse('home'))
        self.assertContains(visitor_response, 'Sign in')
        self.assertContains(visitor_response, 'Start workspace')

        user, _practice, _therapist = self.create_practice_user()
        self.client.force_login(user)
        user_response = self.client.get(reverse('home'))
        self.assertContains(user_response, 'Open dashboard')
        self.assertContains(user_response, 'Sign out')
        self.assertNotContains(user_response, '>Sign in</a>')

    def test_cookie_policy_is_public(self):
        response = self.client.get(reverse('cookie_policy'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cookie Policy')
        self.assertContains(response, 'Session cookies')

    def test_pricing_page_is_public_and_shows_subscription_plans(self):
        response = self.client.get(reverse('pricing'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Fair per-user pricing')
        self.assertContains(response, 'Per active user')
        self.assertContains(response, '$39')
        self.assertContains(response, '/user/month')
        self.assertContains(response, 'Client portal users are included')
        self.assertNotContains(response, '$79')
        self.assertNotContains(response, '$149')
        self.assertContains(response, '10% annual discount')
        self.assertContains(response, 'FAQPage')

    def test_features_page_is_public_and_links_to_seo_pages(self):
        response = self.client.get(reverse('features'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Everything therapists need to run a calmer practice')
        self.assertContains(response, 'Public booking requests')
        self.assertContains(response, reverse('therapy_scheduling_software'))
        self.assertContains(response, reverse('clinical_notes_software'))
        self.assertContains(response, reverse('client_portal_software'))
        self.assertContains(response, reverse('mental_health_billing_software'))

    def test_seo_content_pages_are_public(self):
        pages = [
            ('therapy_practice_management', 'Therapy practice management software'),
            ('therapy_scheduling_software', 'Therapy scheduling software'),
            ('clinical_notes_software', 'Clinical notes software for therapists'),
            ('client_portal_software', 'Client portal software for therapists'),
            ('mental_health_billing_software', 'Mental health billing software'),
        ]

        for route_name, expected_copy in pages:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, expected_copy)
                self.assertContains(response, 'https://nuviamy.com/')
                self.assertContains(response, '/static/favicon.svg')

    def test_robots_and_sitemap_load(self):
        robots = self.client.get(reverse('robots_txt'))
        sitemap = self.client.get(reverse('sitemap_xml'))

        self.assertEqual(robots.status_code, 200)
        self.assertContains(robots, 'Sitemap: https://nuviamy.com/sitemap.xml')
        self.assertEqual(sitemap.status_code, 200)
        self.assertContains(sitemap, '<loc>https://nuviamy.com/</loc>')
        self.assertContains(sitemap, '<loc>https://nuviamy.com/pricing/</loc>')
        self.assertContains(sitemap, '<loc>https://nuviamy.com/features/</loc>')
        self.assertContains(sitemap, '<loc>https://nuviamy.com/therapy-practice-management-software/</loc>')
        self.assertContains(sitemap, '<loc>https://nuviamy.com/therapy-scheduling-software/</loc>')
        self.assertContains(sitemap, '<loc>https://nuviamy.com/clinical-notes-software-for-therapists/</loc>')
        self.assertContains(sitemap, '<loc>https://nuviamy.com/client-portal-software-for-therapists/</loc>')
        self.assertContains(sitemap, '<loc>https://nuviamy.com/mental-health-billing-software/</loc>')

    def test_favicon_redirects_to_svg_icon(self):
        response = self.client.get(reverse('favicon'))

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, '/static/favicon.svg')

    def test_login_page_loads(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sign in to your dashboard')
        self.assertContains(response, 'Email')
        self.assertContains(response, 'Back to home')
        self.assertContains(response, 'Create a practice account')
        self.assertNotContains(response, 'Use Django admin instead')

    def test_help_center_is_public_and_searchable(self):
        response = self.client.get(reverse('help_center'), {'q': 'Gmail'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Help Center')
        self.assertContains(response, 'How do I connect Gmail?')
        self.assertContains(response, reverse('support_contact'))

    def test_monitoring_is_staff_only(self):
        regular_user = get_user_model().objects.create_user(username='regular', password='StrongPass123!')
        self.client.force_login(regular_user)
        self.assertEqual(self.client.get(reverse('staff_monitoring')).status_code, 403)

        self.client.logout()
        staff_user = get_user_model().objects.create_user(username='staff', password='StrongPass123!', is_staff=True)
        self.client.force_login(staff_user)
        response = self.client.get(reverse('staff_monitoring'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Platform monitoring')
        self.assertContains(response, 'Service health')

    def test_public_health_check_returns_ok(self):
        response = self.client.get(reverse('health'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', SUPPORT_EMAIL='support@example.com')
    def test_support_contact_sends_email(self):
        response = self.client.post(reverse('support_contact'), {
            'name': 'Jane Smith',
            'email': 'jane@example.com',
            'topic': 'setup',
            'message': 'I need help connecting Gmail.',
            'website': '',
        })

        self.assertRedirects(response, '/help/contact/?sent=1')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['support@example.com'])
        self.assertIn('connecting Gmail', mail.outbox[0].body)

    def test_support_contact_is_rate_limited(self):
        for _ in range(5):
            response = self.client.post(reverse('support_contact'), {})
            self.assertEqual(response.status_code, 200)

        response = self.client.post(reverse('support_contact'), {})

        self.assertEqual(response.status_code, 429)

    def test_authenticated_user_can_view_dashboard(self):
        user, _practice, _therapist = self.create_practice_user()
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Good')
        self.assertContains(response, 'Laura')
        self.assertContains(response, '+ New client')
        self.assertContains(response, '+ New appointment')
        self.assertContains(response, 'Revenue trend')
        self.assertContains(response, 'Session volume')
        self.assertContains(response, 'Profile settings')
        self.assertContains(response, 'Sign out')
        self.assertNotContains(response, 'href="/admin/"')

    def test_dashboard_tour_can_open_after_checkout(self):
        user, _practice, _therapist = self.create_practice_user()
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard'), {'tour': '1'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Start guided tour')
        self.assertContains(response, 'Guided setup')
        self.assertContains(response, 'Finish setting up your practice')
        self.assertContains(response, 'show-dashboard-tour')
        self.assertContains(response, 'data-tour-spotlight')
        self.assertContains(response, 'target: \'[data-tour-target="setup"]\'')
        self.assertContains(response, 'data-tour-target="nav-appointments"')
        self.assertContains(response, 'data-tour-target="nav-clients"')
        self.assertContains(response, 'data-tour-target="nav-billing"')
        self.assertContains(response, 'data-tour-target="nav-settings"')
        self.assertContains(response, 'data-tour-next')

    def test_dashboard_orders_summary_billing_charts_then_daily_work_without_integration_gate(self):
        user, practice, therapist = self.create_practice_user()
        client = Client.objects.create(practice=practice, first_name='Maya', last_name='Johnson')
        now = timezone.now()
        appointment = Appointment.objects.create(
            practice=practice, client=client, therapist=therapist,
            starts_at=now, ends_at=now + timedelta(minutes=50),
        )
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('clients:detail', args=[client.pk]))
        self.assertContains(response, reverse('appointments:edit', args=[appointment.pk]))
        self.assertContains(response, 'Optional connections')
        self.assertNotContains(response, 'before adding clients')
        self.assertNotContains(response, 'setup-locked')
        html = response.content.decode()
        self.assertLess(html.index('class="stats dashboard-metrics"'), html.index('id="dashboard-billing-title"'))
        self.assertLess(html.index('id="dashboard-billing-title"'), html.index('class="performance-grid"'))
        self.assertLess(html.index('class="performance-grid"'), html.index('id="today"'))

    def test_client_login_redirects_to_portal(self):
        practice = Practice.objects.create(name='Nuvia Therapy')
        portal_client = Client.objects.create(practice=practice, first_name='Maya', last_name='Johnson')
        user = get_user_model().objects.create_user(username='maya', email='maya@example.com', password='StrongPass123!')
        UserProfile.objects.create(user=user, practice=practice, role=UserProfile.Role.CLIENT)
        ClientPortalAccess.objects.create(user=user, practice=practice, client=portal_client, is_active=True)

        response = self.client.post(reverse('login'), {
            'username': 'maya@example.com',
            'password': 'StrongPass123!',
        })

        self.assertRedirects(response, reverse('portal:dashboard'))

    def test_client_cannot_view_practice_dashboard(self):
        practice = Practice.objects.create(name='Nuvia Therapy')
        portal_client = Client.objects.create(practice=practice, first_name='Maya', last_name='Johnson')
        user = get_user_model().objects.create_user(username='maya', password='StrongPass123!')
        UserProfile.objects.create(user=user, practice=practice, role=UserProfile.Role.CLIENT)
        ClientPortalAccess.objects.create(user=user, practice=practice, client=portal_client, is_active=True)
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard'))

        self.assertRedirects(response, reverse('portal:dashboard'))

    def test_client_cannot_view_practice_clients_page(self):
        practice = Practice.objects.create(name='Nuvia Therapy')
        portal_client = Client.objects.create(practice=practice, first_name='Maya', last_name='Johnson')
        user = get_user_model().objects.create_user(username='maya', password='StrongPass123!')
        UserProfile.objects.create(user=user, practice=practice, role=UserProfile.Role.CLIENT)
        ClientPortalAccess.objects.create(user=user, practice=practice, client=portal_client, is_active=True)
        self.client.force_login(user)

        response = self.client.get(reverse('clients:list'))

        self.assertRedirects(response, reverse('portal:dashboard'))

    def test_dashboard_shows_today_appointments(self):
        user, practice, therapist = self.create_practice_user()
        client = Client.objects.create(
            practice=practice,
            primary_therapist=therapist,
            first_name='Maya',
            last_name='Johnson',
            status=Client.Status.ACTIVE,
        )
        starts_at = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0)
        Appointment.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(hours=1),
            appointment_type=Appointment.AppointmentType.VIDEO,
        )

        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Today's appointments")
        self.assertContains(response, 'Maya Johnson')
        self.assertContains(response, 'Video Call')

    def test_dashboard_scopes_appointments_to_user_practice(self):
        user, practice, therapist = self.create_practice_user()
        _other_user, other_practice, other_therapist = self.create_practice_user(
            username='other',
            practice_name='Other Practice',
        )
        client = Client.objects.create(
            practice=practice,
            primary_therapist=therapist,
            first_name='Visible',
            last_name='Client',
        )
        other_client = Client.objects.create(
            practice=other_practice,
            primary_therapist=other_therapist,
            first_name='Hidden',
            last_name='Client',
        )
        starts_at = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0)
        Appointment.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(hours=1),
        )
        Appointment.objects.create(
            practice=other_practice,
            client=other_client,
            therapist=other_therapist,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(hours=1),
        )

        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Visible Client')
        self.assertNotContains(response, 'Hidden Client')

    def test_dashboard_shows_empty_appointment_state(self):
        user, _practice, _therapist = self.create_practice_user()
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No appointments scheduled for today.')

    def test_dashboard_shows_treatment_plan_reviews_due_task(self):
        user, practice, therapist = self.create_practice_user()
        client = Client.objects.create(
            practice=practice,
            primary_therapist=therapist,
            first_name='Maya',
            last_name='Johnson',
        )
        TreatmentPlan.objects.create(
            practice=practice,
            client=client,
            therapist=therapist,
            title='Due care plan',
            goals='Review goals.',
            review_date=timezone.localdate(),
        )

        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Treatment plan reviews')
        self.assertContains(response, '1 treatment plan due for review')

    def test_team_member_can_create_and_complete_assigned_task(self):
        user, practice, _therapist = self.create_practice_user()
        self.client.force_login(user)

        response = self.client.post(reverse('tasks_create'), {
            'title': 'Review intake packet',
            'description': 'Confirm the packet is ready before the first session.',
            'assignee': user.pk,
            'due_date': timezone.localdate().isoformat(),
            'priority': Task.Priority.HIGH,
            'status': Task.Status.OPEN,
        })

        task = Task.objects.get(practice=practice)
        self.assertRedirects(response, reverse('tasks_list'))
        self.assertEqual(task.assignee, user)
        self.assertContains(self.client.get(reverse('dashboard')), 'Review intake packet')

        response = self.client.post(reverse('tasks_status', args=[task.pk]), {'status': Task.Status.DONE})
        self.assertRedirects(response, reverse('tasks_list'))
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.DONE)

    def test_therapist_without_task_view_permission_is_forbidden(self):
        user, _practice, _therapist = self.create_practice_user()
        profile = user.nuvia_profile
        profile.role = UserProfile.Role.THERAPIST
        profile.permissions = {'tasks': {'view': False, 'create': False, 'edit': False, 'delete': False}}
        profile.save(update_fields=['role', 'permissions', 'updated_at'])

        self.client.force_login(user)
        response = self.client.get(reverse('tasks_list'))

        self.assertRedirects(response, reverse('dashboard'))

    def test_dashboard_scopes_treatment_plan_reviews_to_user_practice(self):
        user, _practice, _therapist = self.create_practice_user()
        _other_user, other_practice, other_therapist = self.create_practice_user(
            username='other',
            practice_name='Other Practice',
        )
        other_client = Client.objects.create(
            practice=other_practice,
            primary_therapist=other_therapist,
            first_name='Hidden',
            last_name='Client',
        )
        TreatmentPlan.objects.create(
            practice=other_practice,
            client=other_client,
            therapist=other_therapist,
            title='Hidden due plan',
            goals='Hidden goals.',
            review_date=timezone.localdate(),
        )

        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Treatment plan reviews')

    def test_staff_user_can_see_admin_link(self):
        user = get_user_model().objects.create_user(
            username='staff',
            password='StrongPass123!',
            is_staff=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/admin/"')

    def test_logout_redirects_to_login(self):
        user = get_user_model().objects.create_user(username='admin', password='StrongPass123!')
        self.client.force_login(user)
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('login'))
