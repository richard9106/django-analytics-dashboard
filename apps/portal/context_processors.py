from apps.accounts.access import get_practice_for_user, is_client_user
from apps.practices.models import ExternalIntegration
from .models import ClientPortalRequest


def portal_request_badge(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or is_client_user(user):
        return {'open_portal_request_count': 0, 'google_workspace_connected': False}

    practice = get_practice_for_user(user)
    if not practice:
        return {'open_portal_request_count': 0, 'google_workspace_connected': False}

    return {
        'open_portal_request_count': ClientPortalRequest.objects.filter(
            practice=practice,
            status__in=[ClientPortalRequest.Status.NEW, ClientPortalRequest.Status.REVIEWED],
        ).count(),
        'google_workspace_connected': ExternalIntegration.objects.filter(
            practice=practice,
            provider=ExternalIntegration.Provider.GOOGLE,
            status=ExternalIntegration.Status.CONNECTED,
        ).exists(),
    }
