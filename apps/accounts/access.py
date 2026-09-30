from django.contrib import messages
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme

from .models import UserProfile

PERMISSION_RESOURCES = (
    ('clients', 'Clients'),
    ('appointments', 'Appointments'),
    ('clinical', 'Notes & treatment'),
    ('billing', 'Billing'),
    ('documents', 'Documents'),
    ('intake', 'Intake'),
    ('requests', 'Requests'),
    ('tasks', 'Tasks'),
)
PERMISSION_ACTIONS = (
    ('view', 'Read'),
    ('create', 'Create'),
    ('edit', 'Edit'),
    ('delete', 'Delete'),
)

DEFAULT_THERAPIST_PERMISSIONS = {
    'clients': {'view': True, 'create': True, 'edit': True, 'delete': False},
    'appointments': {'view': True, 'create': True, 'edit': True, 'delete': False},
    'clinical': {'view': True, 'create': True, 'edit': True, 'delete': False},
    'billing': {'view': False, 'create': False, 'edit': False, 'delete': False},
    'documents': {'view': True, 'create': True, 'edit': True, 'delete': False},
    'intake': {'view': True, 'create': True, 'edit': True, 'delete': False},
    'requests': {'view': True, 'create': False, 'edit': True, 'delete': False},
    'tasks': {'view': True, 'create': True, 'edit': True, 'delete': False},
}


def is_client_user(user):
    profile = getattr(user, 'nuvia_profile', None)
    return bool((profile and profile.role == UserProfile.Role.CLIENT) or getattr(user, 'client_portal_access', None))


def must_change_password(user):
    profile = getattr(user, 'nuvia_profile', None)
    return bool(profile and profile.must_change_password)


class ForcePasswordChangeRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and must_change_password(request.user):
            return redirect('force_password_change')
        return super().dispatch(request, *args, **kwargs)


def get_practice_for_user(user):
    profile = getattr(user, 'nuvia_profile', None)
    if profile and profile.role != UserProfile.Role.CLIENT:
        return profile.practice

    therapist_profile = getattr(user, 'therapist_profile', None)
    if therapist_profile:
        return therapist_profile.practice

    return None


class ClientPortalRedirectMixin:
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and is_client_user(request.user):
            return redirect('portal:dashboard')
        return super().dispatch(request, *args, **kwargs)


def has_practice_permission(user, resource, action):
    profile = getattr(user, 'nuvia_profile', None)
    if not profile or profile.role in {UserProfile.Role.OWNER, UserProfile.Role.ADMIN}:
        return bool(profile and profile.role != UserProfile.Role.CLIENT)
    if profile.role != UserProfile.Role.THERAPIST:
        return False
    permissions = profile.permissions or DEFAULT_THERAPIST_PERMISSIONS
    return bool(permissions.get(resource, {}).get(action, False))


def permission_redirect(request, message='That area is not available with your current workspace permissions.'):
    """Return a safe, friendly response without weakening the server-side check."""
    messages.warning(request, message)
    referer = request.META.get('HTTP_REFERER', '')
    current = request.build_absolute_uri()
    if referer and referer != current and url_has_allowed_host_and_scheme(
        referer, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(referer)
    return redirect('dashboard')


def permission_context(request):
    """Expose the same permission model to navigation and server-rendered actions."""
    user = getattr(request, 'user', None)
    return {
        'workspace_permissions': {
            resource: {
                action: has_practice_permission(user, resource, action)
                for action, _label in PERMISSION_ACTIONS
            }
            for resource, _label in PERMISSION_RESOURCES
        },
        'can_manage_team': bool(
            user and user.is_authenticated and not is_client_user(user)
            and getattr(getattr(user, 'nuvia_profile', None), 'role', None)
            in {UserProfile.Role.OWNER, UserProfile.Role.ADMIN}
        ),
    }


class PracticePermissionMixin:
    permission_resource = None
    permission_action = 'view'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not is_client_user(request.user) and not has_practice_permission(
            request.user, self.permission_resource, self.permission_action
        ):
            return permission_redirect(
                request,
                'You do not have access to that workspace area. We brought you back to a safe page.',
            )
        return super().dispatch(request, *args, **kwargs)
