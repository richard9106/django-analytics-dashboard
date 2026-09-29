from django.shortcuts import redirect

from .models import UserProfile

PERMISSION_RESOURCES = (
    ('clients', 'Clients'),
    ('appointments', 'Appointments'),
    ('clinical', 'Notes & treatment'),
    ('billing', 'Billing'),
    ('documents', 'Documents'),
    ('intake', 'Intake'),
    ('requests', 'Requests'),
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


class PracticePermissionMixin:
    permission_resource = None
    permission_action = 'view'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not is_client_user(request.user) and not has_practice_permission(
            request.user, self.permission_resource, self.permission_action
        ):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied('You do not have permission for this workspace.')
        return super().dispatch(request, *args, **kwargs)
