from apps.accounts.models import UserProfile
from apps.accounts.access import get_practice_for_user


def scope_sessions(queryset, user):
    practice = get_practice_for_user(user)
    if not practice:
        return queryset.none()
    queryset = queryset.filter(practice=practice)
    profile = getattr(user, 'nuvia_profile', None)
    if profile and profile.role in {UserProfile.Role.OWNER, UserProfile.Role.ADMIN}:
        return queryset
    return queryset.filter(therapist__user=user)


def manages_sessions(user):
    profile = getattr(user, 'nuvia_profile', None)
    return bool(profile and profile.role in {UserProfile.Role.OWNER, UserProfile.Role.ADMIN})
