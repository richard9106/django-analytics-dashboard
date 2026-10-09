from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.template import Context, Template
from django.test import RequestFactory, TestCase, override_settings
from django.urls import resolve, reverse, reverse_lazy

from apps.accounts.models import UserProfile
from apps.clients.models import Client
from apps.portal.models import IntakePacketTemplate
from apps.practices.models import Practice
from apps.dashboard.templatetags.workspace_navigation import workspace_breadcrumb_items


@override_settings(MFA_REQUIRED=False)
class WorkspaceBreadcrumbTests(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(name='Breadcrumb clinic')
        self.owner = get_user_model().objects.create_user(username='breadcrumb-owner', is_staff=True)
        UserProfile.objects.create(user=self.owner, practice=self.practice, role=UserProfile.Role.OWNER)
        self.client_record = Client.objects.create(practice=self.practice, first_name='Maya', last_name='Johnson')
        self.template = IntakePacketTemplate.objects.create(practice=self.practice, name='Admission form', questions=['Your goals?'])

    def context(self, route, args=None, **extra):
        path = reverse(route, args=args)
        request = RequestFactory().get(path)
        request.resolver_match = resolve(path)
        request.user = self.owner
        context = {'request': request, 'practice': self.practice, 'can_manage_team': True,
                   'workspace_permissions': {key: {'view': True, 'edit': True} for key in
                                             ['clients', 'appointments', 'clinical', 'billing', 'documents', 'intake', 'requests', 'tasks']}}
        context.update(extra)
        return Context(context)

    def test_menu_sections_have_current_page_and_real_parent_links(self):
        cases = {
            'dashboard': ['Overview'], 'clients:list': ['Overview', 'Clients'],
            'appointments:list': ['Overview', 'Appointments'],
            'clinical:list': ['Overview', 'Notes & Treatment', 'Notes'],
            'clinical:treatment_plans': ['Overview', 'Notes & Treatment', 'Treatment plans'],
            'billing:list': ['Overview', 'Billing'], 'documents:list': ['Overview', 'Documents'],
            'intake:list': ['Overview', 'Intake'], 'portal_requests:list': ['Overview', 'Requests'],
            'portal_requests:conversations': ['Overview', 'Requests', 'Messages'],
            'settings:insurance': ['Overview', 'Settings', 'Insurance'],
            'settings:package_templates': ['Overview', 'Settings', 'Session packages'],
            'practice_settings:integrations': ['Overview', 'Settings', 'Integrations'],
            'profile_settings': ['Overview', 'Profile settings'],
            'team_management': ['Overview', 'Settings', 'Team'],
            'tasks_list': ['Overview', 'Tasks'], 'staff_monitoring': ['Overview', 'Monitoring'],
            'help_center': ['Overview', 'Help Center'],
            'support_contact': ['Overview', 'Help Center', 'Contact support'],
        }
        for route, expected in cases.items():
            with self.subTest(route=route):
                crumbs = workspace_breadcrumb_items(self.context(route))
                self.assertEqual([crumb['label'] for crumb in crumbs], expected)
                self.assertIsNone(crumbs[-1]['url'])
                for crumb in crumbs[:-1]:
                    if crumb['url']:
                        resolve(crumb['url'].split('#')[0])

    def test_intake_edit_retains_library_and_record_without_extra_queries(self):
        context = self.context('intake:template_edit', [self.template.pk], intake_template=self.template)
        with self.assertNumQueries(0):
            crumbs = workspace_breadcrumb_items(context)
        self.assertEqual([crumb['label'] for crumb in crumbs], ['Overview', 'Intake', 'Template library', 'Admission form', 'Edit template'])
        self.assertEqual(crumbs[2]['url'], reverse('intake:list') + '#intake-template-library')

    def test_patient_trail_and_existing_portal_links_remain_clickable(self):
        context = self.context('clients:edit', [self.client_record.pk], object=self.client_record)
        crumbs = workspace_breadcrumb_items(context)
        self.assertEqual([crumb['label'] for crumb in crumbs], ['Overview', 'Clients', 'Maya Johnson', 'Edit client'])
        self.assertEqual(crumbs[2]['url'], reverse('clients:detail', args=[self.client_record.pk]))
        context = self.context('portal_settings:portal_access', breadcrumbs=[
            {'label': 'Clients', 'url': reverse('clients:list')},
            {'label': 'Maya Johnson', 'url': reverse('clients:detail', args=[self.client_record.pk])},
            {'label': 'Portal access'},
        ])
        self.assertEqual(workspace_breadcrumb_items(context)[2]['url'], reverse('clients:detail', args=[self.client_record.pk]))

    def test_scoped_session_context_and_permissions_control_parent_links(self):
        appointment = SimpleNamespace(pk=42, practice_id=self.practice.pk)
        context = self.context('billing:invoice_create', workflow_appointment=appointment)
        crumbs = workspace_breadcrumb_items(context)
        self.assertEqual([crumb['label'] for crumb in crumbs], ['Overview', 'Appointments', 'Session #42', 'New invoice'])
        context['workspace_permissions']['appointments']['edit'] = False
        self.assertIsNone(workspace_breadcrumb_items(context)[2]['url'])
        context['workspace_permissions']['clients']['view'] = False
        patient_context = self.context('clients:edit', [self.client_record.pk], object=self.client_record,
                                       workspace_permissions=context['workspace_permissions'])
        self.assertIsNone(workspace_breadcrumb_items(patient_context)[2]['url'])

    def test_availability_parent_retains_validated_calendar_filters(self):
        calendar_url = reverse('appointments:list') + '?view=week&date=2026-10-06'
        context = self.context('appointments:availability_edit', [7], calendar_return_url=calendar_url)
        self.assertEqual(workspace_breadcrumb_items(context)[1]['url'], calendar_url)
        self.assertEqual(workspace_breadcrumb_items(context)[2]['url'], calendar_url + '#availability-changes')
        context['calendar_return_url'] = 'https://example.com/appointments/'
        self.assertEqual(workspace_breadcrumb_items(context)[1]['url'], reverse('appointments:list'))
        context['calendar_return_url'] = reverse_lazy('appointments:list')
        self.assertEqual(workspace_breadcrumb_items(context)[1]['url'], reverse('appointments:list'))

    def test_foreign_record_and_untrusted_query_parameters_do_not_name_records(self):
        foreign_practice = Practice.objects.create(name='Other clinic')
        foreign = IntakePacketTemplate.objects.create(practice=foreign_practice, name='Hidden form', questions=['Hidden question'])
        context = self.context('intake:template_edit', [foreign.pk], intake_template=foreign)
        self.assertNotIn('Hidden form', [crumb['label'] for crumb in workspace_breadcrumb_items(context)])
        context = self.context('clinical:diagnosis_create')
        context['request'].GET = {'client': str(self.client_record.pk), 'return_to': 'https://example.com'}
        self.assertNotIn('Maya Johnson', [crumb['label'] for crumb in workspace_breadcrumb_items(context)])

    def test_breadcrumbs_are_escaped_and_only_last_item_is_current(self):
        self.template.name = '<script>unsafe</script>'
        context = self.context('intake:template_edit', [self.template.pk], intake_template=self.template)
        rendered = Template("{% include 'partials/breadcrumbs.html' %}").render(context)
        self.assertNotIn('<script>unsafe</script>', rendered)
        self.assertIn('&lt;script&gt;unsafe&lt;/script&gt;', rendered)
        self.assertEqual(rendered.count('aria-current="page"'), 1)
        self.assertIn('<ol>', rendered)

    def test_anonymous_client_portal_and_auth_challenge_do_not_link_to_workspace(self):
        context = self.context('help_center')
        context['request'].user = AnonymousUser()
        self.assertEqual(workspace_breadcrumb_items(context), [])
        patient_user = get_user_model().objects.create_user(username='breadcrumb-patient')
        UserProfile.objects.create(user=patient_user, practice=self.practice, role=UserProfile.Role.CLIENT)
        context['request'].user = patient_user
        self.assertEqual(workspace_breadcrumb_items(context), [])
        self.assertEqual(workspace_breadcrumb_items(self.context('mfa_challenge')), [])

    def test_standalone_payment_and_errors_have_trail_without_duplicate_modal_navigation(self):
        self.client.force_login(self.owner)
        url = reverse('billing:payment_create')
        for response in [self.client.get(url), self.client.post(url, {})]:
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'aria-label="Breadcrumb"', count=1)
            self.assertContains(response, 'aria-current="page"', count=1)
            self.assertContains(response, 'Record payment')
        response = self.client.get(reverse('billing:list'))
        self.assertContains(response, 'aria-label="Breadcrumb"', count=1)

    def test_representative_workspace_gets_render_one_shared_navigation(self):
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
                self.assertContains(response, 'aria-label="Breadcrumb"', count=1)
                trail = response.content.decode().split('aria-label="Breadcrumb">', 1)[1].split('</nav>', 1)[0]
                self.assertEqual(trail.count('aria-current="page"'), 1)
