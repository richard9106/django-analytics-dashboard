"""Account setup links never expose a password to an administrator."""
from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator, default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import base36_to_int, urlsafe_base64_encode


class InvitationTokenGenerator(PasswordResetTokenGenerator):
    key_salt = 'nuviamy.account-invitation.v1'

    def make_token(self, user):
        from .models import AccountSecurity
        AccountSecurity.objects.get_or_create(user=user)
        return super().make_token(user)

    def _make_hash_value(self, user, timestamp):
        from .models import UserProfile, AccountSecurity
        from apps.portal.models import ClientPortalAccess
        profile = UserProfile.objects.filter(user=user).values('practice_id', 'role', 'updated_at').first()
        access = ClientPortalAccess.objects.filter(user=user).values('practice_id', 'is_active', 'updated_at').first()
        version = AccountSecurity.objects.filter(user=user).values_list('session_version', flat=True).first()
        return super()._make_hash_value(user, timestamp) + str(user.is_active) + str(profile) + str(access) + str(version)

    def check_token(self, user, token):
        if not user or user.has_usable_password() or not user.is_active:
            return False
        access = getattr(user, 'client_portal_access', None)
        if access is not None and not access.is_active:
            return False
        if not super().check_token(user, token):
            return False
        timestamp = base36_to_int(token.split('-')[0])
        return self._num_seconds(self._now()) - timestamp <= 48 * 60 * 60


invitation_token_generator = InvitationTokenGenerator()


def send_account_access_email(request, user):
    """Rotate pending invitations; never replace an established password on resend."""
    if not user.is_active or not user.email:
        return False
    access = getattr(user, 'client_portal_access', None)
    if access is not None and not access.is_active:
        return False
    from django.contrib.auth import get_user_model
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().get(pk=user.pk)
        if not user.is_active or not user.email:
            return False
        from apps.portal.models import ClientPortalAccess
        if ClientPortalAccess.objects.filter(user=user, is_active=False).exists():
            return False
        pending = not user.has_usable_password()
        if pending:
            user.set_unusable_password()  # New nonce invalidates earlier invitation links.
            user.save(update_fields=['password'])
        generator = invitation_token_generator if pending else default_token_generator
        name = 'account_invitation' if pending else 'password_reset_confirm'
        link = request.build_absolute_uri(reverse(name, kwargs={
            'uidb64': urlsafe_base64_encode(force_bytes(user.pk)), 'token': generator.make_token(user)}))
    subject = 'Set up your NuviaMy account' if pending else 'Reset your NuviaMy password'
    body = ('Hello,\n\n' + ('Set your password using this one-time link (valid for up to 48 hours):\n' if pending
            else 'Choose a new password using this one-time link:\n') + link
            + '\n\nIf you did not expect this email, ignore it. Your existing password, if any, stays unchanged until you complete the reset.\n'
            + 'Do not reply with passwords or personal health information.\n')
    return send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False) == 1
