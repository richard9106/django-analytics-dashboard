from django.shortcuts import redirect

from .models import UserProfile


def is_client_user(user):
    profile = getattr(user, 'nuvia_profile', None)
    return bool((profile and profile.role == UserProfile.Role.CLIENT) or getattr(user, 'client_portal_access', None))


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
