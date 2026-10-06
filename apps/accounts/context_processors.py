import time
from django.conf import settings
from .security import requires_mfa, verified


def security_context(request):
    if not request.user.is_authenticated or not hasattr(request, 'account_security'):
        return {}
    now = time.time()
    pending = requires_mfa(request.user) and not verified(request, request.account_security)
    remaining = settings.SECURITY_CHALLENGE_TIMEOUT - (now - request.session.get('security_password_at', 0)) if pending else settings.SECURITY_ABSOLUTE_TIMEOUT - (now - request.session.get('security_started_at', 0))
    return {'security_pending': pending, 'security_deadline_seconds': max(0, int(remaining)), 'security_idle_seconds': settings.SECURITY_IDLE_TIMEOUT}
