import hashlib
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import EarlyAccessInvitation


def invitation_for(token, email=None, lock=False):
    query = EarlyAccessInvitation.objects
    if lock:
        query = query.select_for_update()
    invitation = query.filter(token_hash=hashlib.sha256(token.encode()).hexdigest()).first()
    if not invitation or invitation.redeemed_at or invitation.expires_at <= timezone.now():
        raise ValidationError("This invitation is invalid, expired, or already used.")
    if email and invitation.email.casefold() != email.casefold():
        raise ValidationError("Use the email address this invitation was issued to.")
    return invitation


def assert_free_seat_available(practice, exclude_user_id=None):
    from apps.billing.access import subscription_access
    access = subscription_access(practice)
    if access.get('free_access') != 'early_access':
        return
    profiles = practice.user_profiles.filter(user__is_active=True, role__in=['owner', 'admin', 'therapist'])
    if exclude_user_id:
        profiles = profiles.exclude(user_id=exclude_user_id)
    if profiles.exists():
        raise ValidationError("Your private invitation includes one internal user. Choose a paid subscription before adding a team member; paid billing begins when you confirm it.")
