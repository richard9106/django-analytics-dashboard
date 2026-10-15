from django.contrib.auth import get_user_model
from django.contrib.auth.views import PasswordResetConfirmView, INTERNAL_RESET_SESSION_TOKEN
from django.db import transaction
from django.urls import reverse_lazy
from django.utils import timezone
from apps.rate_limit import PostRateLimitMixin
from .invitations import invitation_token_generator
from .models import UserProfile


class AccountPasswordConfirmView(PostRateLimitMixin, PasswordResetConfirmView):
    rate_limit_scope = 'account_password_confirm'
    rate_limit_count = 20
    rate_limit_seconds = 900
    template_name = 'registration/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')

    def form_valid(self, form):
        with transaction.atomic():
            locked = get_user_model().objects.select_for_update().get(pk=self.user.pk)
            token = self.request.session.get(INTERNAL_RESET_SESSION_TOKEN, '')
            if not locked.is_active or not self.token_generator.check_token(locked, token):
                self.validlink = False
                return self.render_to_response(self.get_context_data())
            form.user = locked
            response = super().form_valid(form)
            UserProfile.objects.filter(user=locked, must_change_password=True).update(must_change_password=False)
            from apps.portal.models import ClientPortalAccess
            ClientPortalAccess.objects.filter(user=locked, accepted_at__isnull=True).update(accepted_at=timezone.now())
            return response


class AccountInvitationView(AccountPasswordConfirmView):
    token_generator = invitation_token_generator
    template_name = 'accounts/invitation.html'
