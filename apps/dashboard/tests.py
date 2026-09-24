from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.appointments.models import Appointment
from apps.clinical.models import TreatmentPlan
from apps.clients.models import Client
from apps.portal.models import ClientPortalAccess
from apps.practices.models import Practice, TherapistProfile


class DashboardTests(TestCase):
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
        self.assertContains(response, reverse('pricing'))

    def test_pricing_page_is_public_and_shows_subscription_plans(self):
        response = self.client.get(reverse('pricing'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Subscription pricing')
        self.assertContains(response, 'Solo Therapist')
        self.assertContains(response, '$39')
        self.assertContains(response, 'Group Practice')
        self.assertContains(response, '$79')
        self.assertContains(response, 'Clinic')
        self.assertContains(response, '$149')
        self.assertContains(response, '10% annual discount')
        self.assertContains(response, 'FAQPage')

    def test_robots_and_sitemap_load(self):
        robots = self.client.get(reverse('robots_txt'))
        sitemap = self.client.get(reverse('sitemap_xml'))

        self.assertEqual(robots.status_code, 200)
        self.assertContains(robots, 'Sitemap: https://nuviamy.com/sitemap.xml')
        self.assertEqual(sitemap.status_code, 200)
        self.assertContains(sitemap, '<loc>https://nuviamy.com/</loc>')
        self.assertContains(sitemap, '<loc>https://nuviamy.com/pricing/</loc>')

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

    def test_authenticated_user_can_view_dashboard(self):
        user, _practice, _therapist = self.create_practice_user()
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Good')
        self.assertContains(response, 'Laura')
        self.assertContains(response, '+ New client')
        self.assertContains(response, '+ New appointment')
        self.assertContains(response, 'Profile settings')
        self.assertContains(response, 'Sign out')
        self.assertNotContains(response, 'href="/admin/"')

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
