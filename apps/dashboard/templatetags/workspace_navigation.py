"""Workspace breadcrumbs derived from routes and already-scoped view context."""
from urllib.parse import urlsplit

from django import template
from django.urls import NoReverseMatch, Resolver404, resolve, reverse

register = template.Library()

RESOURCES = {
    'clients': 'clients', 'appointments': 'appointments', 'clinical': 'clinical',
    'billing': 'billing', 'documents': 'documents', 'intake': 'intake',
    'portal_settings': 'intake', 'portal_requests': 'requests', 'settings': 'billing',
}
SECTIONS = {
    'clients': ('Clients', 'clients:list'),
    'appointments': ('Appointments', 'appointments:list'),
    'clinical': ('Notes & Treatment', None),
    'billing': ('Billing', 'billing:list'),
    'documents': ('Documents', 'documents:list'),
    'intake': ('Intake', 'intake:list'),
    'portal_requests': ('Requests', 'portal_requests:list'),
}
ACTIONS = {
    'clients': {'create': 'New client', 'edit': 'Edit client', 'delete': 'Delete client'},
    'appointments': {'create': 'New appointment', 'edit': 'Edit appointment',
                     'reschedule': 'Reschedule appointment', 'sync_issues': 'Sync issues',
                     'availability_edit': 'Edit availability'},
    'clinical': {'create': 'New note', 'edit': 'Edit note', 'delete': 'Delete note',
                 'treatment_plan_create': 'New treatment plan', 'treatment_plan_edit': 'Edit treatment plan',
                 'diagnosis_create': 'New diagnosis', 'diagnosis_edit': 'Edit diagnosis'},
    'billing': {'invoice_create': 'New invoice', 'invoice_edit': 'Edit invoice',
                'package_create': 'New client package', 'package_edit': 'Edit client package',
                'usage_create': 'Record package usage', 'payment_create': 'Record payment'},
    'documents': {'create': 'Upload document'},
    'intake': {'template_create': 'New template', 'template_edit': 'Edit template',
               'assign': 'Assign intake', 'responses': 'Responses'},
}


def _url(context, route, args=None, fragment='', kwargs=None):
    if not route:
        return None
    resource = RESOURCES.get(route.partition(':')[0])
    if route in {'practice_settings:availability', 'practice_settings:working_hour_create'}:
        resource = 'appointments'
    elif route in {'tasks_list', 'tasks_create'}:
        resource = 'tasks'
    permissions = context.get('workspace_permissions', {})
    if resource and not permissions.get(resource, {}).get('view', False):
        return None
    if route == 'team_management' and not context.get('can_manage_team'):
        return None
    try:
        return reverse(route, args=args, kwargs=kwargs) + fragment
    except NoReverseMatch:
        return None


def _scoped(context, obj):
    practice = context.get('practice')
    if obj is None or practice is None or getattr(obj, 'practice_id', None) != practice.pk:
        return None
    return obj


def _safe_existing_url(context, url):
    if not url:
        return None
    url = str(url)
    if not url.startswith('/') or url.startswith('//'):
        return None
    try:
        match = resolve(urlsplit(url).path)
    except Resolver404:
        return None
    return url if _url(context, match.view_name, args=match.args or None, kwargs=match.kwargs or None) is not None else None


@register.simple_tag(takes_context=True)
def workspace_breadcrumb_items(context):
    request = context.get('request')
    if request is None or not getattr(getattr(request, 'user', None), 'is_authenticated', False):
        return []
    profile = getattr(request.user, 'nuvia_profile', None)
    if (profile and profile.role == 'client') or (profile is None and not getattr(request.user, 'is_staff', False)):
        return []
    match = getattr(request, 'resolver_match', None)
    if not match:
        return []
    namespace, name = match.namespace, match.url_name
    crumbs = [{'label': 'Overview', 'url': _url(context, 'dashboard')}]

    def add(label, route=None, args=None, fragment=''):
        crumbs.append({'label': label, 'url': _url(context, route, args, fragment)})

    # Existing patient-aware trails are produced by tenant-scoped views.
    explicit = context.get('breadcrumbs')
    if explicit:
        for crumb in explicit:
            if crumb.get('label') != 'Overview':
                crumbs.append({'label': crumb['label'], 'url': _safe_existing_url(context, crumb.get('url'))})
    elif namespace in SECTIONS:
        label, route = SECTIONS[namespace]
        add(label, route)
        obj = _scoped(context, context.get('object'))
        if namespace == 'clients':
            client = _scoped(context, context.get('client')) or obj
            if name in {'edit', 'delete'} and client:
                add(str(client), 'clients:detail', [client.pk])
            elif name == 'detail' and client:
                add(str(client))
        elif namespace == 'appointments':
            if name == 'edit' and obj:
                add(f'Session #{obj.pk}')
            elif name == 'availability_edit':
                calendar_url = _safe_existing_url(context, context.get('calendar_return_url'))
                if calendar_url and resolve(urlsplit(calendar_url).path).view_name == 'appointments:list':
                    crumbs[-1]['url'] = calendar_url
                add('Availability changes', 'appointments:list', fragment='#availability-changes')
                if calendar_url and resolve(urlsplit(calendar_url).path).view_name == 'appointments:list':
                    crumbs[-1]['url'] = calendar_url.partition('#')[0] + '#availability-changes'
        elif namespace == 'clinical':
            if name.startswith('diagnosis_'):
                patient = _scoped(context, context.get('diagnosis_patient'))
                if patient:
                    crumbs = crumbs[:1]
                    add('Clients', 'clients:list')
                    add(str(patient), 'clients:detail', [patient.pk])
                else:
                    add('Treatment plans', 'clinical:treatment_plans')
            elif name.startswith('treatment_plan'):
                add('Treatment plans', 'clinical:treatment_plans')
                if name == 'treatment_plan_edit' and obj:
                    add(f'Treatment plan #{obj.pk}')
            else:
                add('Notes', 'clinical:list')
                if name == 'edit' and obj:
                    add(f'Note #{obj.pk}')
        elif namespace == 'intake':
            if name.startswith('template_'):
                add('Template library', 'intake:list', fragment='#intake-template-library')
                intake_template = _scoped(context, context.get('intake_template'))
                if intake_template:
                    add(intake_template.name)
            elif name == 'responses':
                assignment = _scoped(context, context.get('assignment'))
                if assignment:
                    packet = assignment.template_snapshot.get('name')
                    if packet:
                        add(packet)
        elif namespace == 'portal_requests' and name in {'conversations', 'conversation_detail'}:
            add('Messages', 'portal_requests:conversations')
            if name == 'conversation_detail':
                add('Conversation')
        elif namespace == 'billing' and obj:
            if name == 'invoice_edit':
                add(obj.invoice_number)
            elif name == 'package_edit':
                add(obj.name)
        if name in ACTIONS.get(namespace, {}):
            # Session-linked create forms keep a validated parent session.
            appointment = _scoped(context, context.get('workflow_appointment'))
            if appointment and namespace in {'clinical', 'billing'}:
                crumbs = crumbs[:1]
                add('Appointments', 'appointments:list')
                add(f'Session #{appointment.pk}', 'appointments:edit', [appointment.pk])
                # Editing appointments requires edit permission as well.
                if not context.get('workspace_permissions', {}).get('appointments', {}).get('edit', False):
                    crumbs[-1]['url'] = None
            add(ACTIONS[namespace][name])
    elif namespace in {'settings', 'portal_settings', 'practice_settings'}:
        if namespace == 'practice_settings' and name == 'google_workspace':
            add('My Google workspace')
        else:
            add('Settings')
            if namespace == 'portal_settings':
                add('Client portal', 'portal_settings:portal_access')
                if name != 'portal_access':
                    add({'portal_access_create': 'New portal access', 'portal_access_edit': 'Edit portal access'}.get(name, 'Portal access'))
            elif namespace == 'settings':
                insurance = name.startswith('insurance')
                section = 'Insurance' if insurance else 'Session packages'
                add(section, 'settings:insurance' if insurance else 'settings:package_templates')
                if name not in {'insurance', 'package_templates'}:
                    obj = _scoped(context, context.get('object'))
                    if obj and name in {'insurance_payer_edit', 'package_template_edit'}:
                        add(obj.name)
                    elif obj and name == 'insurance_rate_edit':
                        add(f'Rate #{obj.pk}')
                    actions = {
                        'insurance_payer_create': 'New payer', 'insurance_payer_edit': 'Edit payer',
                        'insurance_rate_create': 'New rate', 'insurance_rate_edit': 'Edit rate',
                        'package_template_create': 'New package template', 'package_template_edit': 'Edit package template',
                    }
                    add(actions.get(name, name.replace('_', ' ').capitalize()))
            elif name in {'availability', 'working_hour_create'}:
                crumbs = crumbs[:1]
                add('Appointments', 'appointments:list')
                add('Weekly availability', 'practice_settings:availability')
                if name == 'working_hour_create':
                    add('New working hours')
            else:
                add('Integrations', 'practice_settings:integrations')
    else:
        root_pages = {
            'dashboard': [], 'profile_settings': [('Profile settings', None)],
            'team_management': [('Settings', None), ('Team', None)],
            'tasks_list': [('Tasks', None)], 'tasks_create': [('Tasks', 'tasks_list'), ('New task', None)],
            'staff_monitoring': [('Monitoring', None)], 'help_center': [('Help Center', None)],
            'support_contact': [('Help Center', 'help_center'), ('Contact support', None)],
            'security_settings': [('Profile settings', 'profile_settings'), ('Account security', None)],
            'mfa_setup': [('Profile settings', 'profile_settings'), ('Account security', 'security_settings'), ('Authenticator setup', None)],
            'mfa_recovery_codes': [('Profile settings', 'profile_settings'), ('Account security', 'security_settings'), ('Recovery codes', None)],
            'security_reauthenticate': [('Profile settings', 'profile_settings'), ('Account security', 'security_settings'), ('Confirm password', None)],
        }
        if name not in root_pages:
            return []
        for label, route in root_pages[name]:
            add(label, route)
    crumbs[-1]['url'] = None
    return crumbs
