from .models import AuditLog


def get_request_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def get_audit_practice(user):
    portal_access = getattr(user, 'client_portal_access', None)
    if portal_access:
        return portal_access.practice

    profile = getattr(user, 'nuvia_profile', None)
    if profile:
        return profile.practice

    therapist_profile = getattr(user, 'therapist_profile', None)
    if therapist_profile:
        return therapist_profile.practice

    return None


def log_audit_event(request, action, object_type, object_id='', practice=None, metadata=None, actor=None):
    actor = actor if actor is not None else getattr(request, 'user', None)
    if not practice and actor and getattr(actor, 'is_authenticated', False):
        practice = get_audit_practice(actor)

    if not practice:
        return None

    return AuditLog.objects.create(
        practice=practice,
        actor=actor if actor and getattr(actor, 'is_authenticated', False) else None,
        action=action,
        object_type=object_type,
        object_id=str(object_id) if object_id else '',
        metadata=metadata or {},
        ip_address=get_request_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )
