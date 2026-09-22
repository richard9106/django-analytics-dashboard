from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class DashboardTests(TestCase):
    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_login_page_loads(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sign in to your dashboard')
        self.assertContains(response, 'Create a practice account')
        self.assertNotContains(response, 'Use Django admin instead')

    def test_authenticated_user_can_view_dashboard(self):
        user = get_user_model().objects.create_user(
            username='admin',
            password='StrongPass123!',
            first_name='Laura',
        )
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Practice Dashboard')
        self.assertContains(response, 'Laura')
        self.assertContains(response, '+ New appointment')
        self.assertNotContains(response, 'href="/admin/"')

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
