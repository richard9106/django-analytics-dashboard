"""Permission-aware setup actions shared by the dashboard and workspace toolbar."""
from django.urls import reverse

from apps.accounts.access import get_practice_for_user, has_practice_permission


def setup_steps(request, practice=None):
    if hasattr(request, '_workspace_setup_steps'):
        return request._workspace_setup_steps
    practice = practice or get_practice_for_user(request.user)
    steps = []
    if practice:
        if has_practice_permission(request.user, 'clients', 'create') and not practice.clients.exists():
            steps.append({'label': 'Add your first client', 'url': reverse('clients:create'), 'complete': False})
        if has_practice_permission(request.user, 'appointments', 'edit'):
            if not practice.working_hours.exists() and not practice.availability_overrides.exists():
                steps.append({'label': 'Set practice availability', 'url': reverse('appointments:list') + '?view=week#availability-changes', 'complete': False})
        if has_practice_permission(request.user, 'appointments', 'create') and not practice.appointments.exists():
            steps.append({'label': 'Schedule your first session', 'url': reverse('appointments:create'), 'complete': False})
    request._workspace_setup_steps = steps
    return steps
