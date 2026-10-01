from apps.accounts.access import get_practice_for_user, is_client_user
from apps.practices.models import ExternalIntegration
from .models import ClientPortalRequest, PortalConversation, PortalMessage, PublicBookingRequest


def portal_request_badge(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or is_client_user(user):
        access = getattr(user, 'client_portal_access', None) if user and user.is_authenticated else None
        conversations = PortalConversation.objects.filter(practice=access.practice, client=access.client).select_related('client')[:8] if access and access.is_active else []
        unread = PortalMessage.objects.filter(practice=access.practice, conversation__client=access.client, author_kind=PortalMessage.AuthorKind.STAFF, read_at__isnull=True).count() if access and access.is_active else 0
        return {
            'open_portal_request_count': 0,
            'unread_message_count': unread,
            'chat_conversations': conversations,
            'chat_is_client': True,
            'google_workspace_connected': False,
            'practice_setup_complete': True,
            'practice_setup_gmail': False,
            'practice_setup_stripe': False,
        }

    practice = get_practice_for_user(user)
    if not practice:
        return {
            'open_portal_request_count': 0,
            'unread_message_count': 0,
            'chat_conversations': [],
            'chat_is_client': False,
            'google_workspace_connected': False,
            'practice_setup_complete': False,
            'practice_setup_gmail': False,
            'practice_setup_stripe': False,
        }

    gmail_connected = ExternalIntegration.objects.filter(
        practice=practice,
        provider=ExternalIntegration.Provider.GOOGLE,
        status=ExternalIntegration.Status.CONNECTED,
        send_email_enabled=True,
    ).exists()
    stripe_ready = practice.can_receive_client_payments

    portal_request_count = ClientPortalRequest.objects.filter(
        practice=practice,
        status__in=[ClientPortalRequest.Status.NEW, ClientPortalRequest.Status.REVIEWED],
    ).count()
    booking_request_count = PublicBookingRequest.objects.filter(
        practice=practice,
        status=PublicBookingRequest.Status.PENDING,
    ).count()
    unread_message_count = PortalMessage.objects.filter(
        practice=practice,
        author_kind=PortalMessage.AuthorKind.CLIENT,
        read_at__isnull=True,
    ).count()
    conversations = PortalConversation.objects.filter(practice=practice).select_related('client')[:8]
    return {
        'open_portal_request_count': portal_request_count + booking_request_count,
        'unread_message_count': unread_message_count,
        'chat_conversations': conversations,
        'chat_is_client': False,
        'google_workspace_connected': gmail_connected,
        'practice_setup_complete': gmail_connected and stripe_ready,
        'practice_setup_gmail': gmail_connected,
        'practice_setup_stripe': stripe_ready,
    }
