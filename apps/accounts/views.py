from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.views.generic.edit import FormView

from apps.audit.models import AuditLog
from apps.audit.utils import log_audit_event
from .access import is_client_user, must_change_password
from .forms import EmailAuthenticationForm, ForcePasswordChangeForm, PracticeSignupForm


class RoleAwareLoginView(LoginView):
    template_name = "dashboard/login.html"
    authentication_form = EmailAuthenticationForm

    def get_success_url(self):
        if must_change_password(self.request.user):
            return reverse_lazy("force_password_change")
        if is_client_user(self.request.user):
            return reverse_lazy("portal:dashboard")
        return super().get_success_url()


class ForcePasswordChangeView(FormView):
    form_class = ForcePasswordChangeForm
    template_name = "accounts/force_password_change.html"
    success_url = reverse_lazy("portal:dashboard")

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.shortcuts import redirect

            return redirect("login")
        if not must_change_password(request.user):
            from django.shortcuts import redirect

            return redirect("portal:dashboard" if is_client_user(request.user) else "dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.save()
        profile = self.request.user.nuvia_profile
        profile.must_change_password = False
        profile.save(update_fields=["must_change_password", "updated_at"])
        update_session_auth_hash(self.request, self.request.user)
        log_audit_event(
            self.request,
            AuditLog.Action.UPDATE,
            "auth.User",
            self.request.user.pk,
            metadata={"password_changed_by_user": True},
        )
        return super().form_valid(form)


class PracticeSignupView(FormView):
    form_class = PracticeSignupForm
    template_name = "accounts/signup.html"
    success_url = reverse_lazy("dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            from django.shortcuts import redirect

            if is_client_user(request.user):
                return redirect("portal:dashboard")
            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)
