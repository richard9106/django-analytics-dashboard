from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import UserProfile
from apps.clients.models import Client
from apps.portal.models import IntakePacketTemplate
from apps.practices.models import Practice


@override_settings(MFA_REQUIRED=False)
class WorkspaceNavigationTests(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(name='Navigation clinic')
        self.owner = get_user_model().objects.create_user(username='navigation-owner', is_staff=True)
        UserProfile.objects.create(user=self.owner, practice=self.practice, role=UserProfile.Role.OWNER)
        self.client_record = Client.objects.create(practice=self.practice, first_name='Demo', last_name='Client')
        self.template = IntakePacketTemplate.objects.create(practice=self.practice, name='Admission form', questions=['Your goals?'])

    def test_workspace_pages_render_without_breadcrumbs(self):
        self.client.force_login(self.owner)
        routes = ['dashboard', 'clients:list', 'clients:detail', 'clients:edit', 'appointments:list',
                  'clinical:list', 'clinical:treatment_plans', 'billing:list', 'documents:list', 'intake:list',
                  'intake:template_edit', 'portal_requests:list', 'portal_requests:conversations',
                  'settings:insurance', 'settings:package_templates', 'practice_settings:integrations',
                  'portal_settings:portal_access', 'profile_settings', 'team_management', 'tasks_list',
                  'help_center', 'support_contact', 'security_settings']
        for route in routes:
            args = [self.client_record.pk] if route in {'clients:detail', 'clients:edit'} else [self.template.pk] if route == 'intake:template_edit' else None
            with self.subTest(route=route):
                response = self.client.get(reverse(route, args=args))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'aria-label="Breadcrumb"')
