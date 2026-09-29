from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.urls import reverse, reverse_lazy
from django.views.generic import TemplateView
from django.views.generic.edit import FormView

from .access import get_practice_for_user, is_client_user, must_change_password
from apps.audit.models import AuditLog
from apps.audit.utils import log_audit_event
from apps.billing.models import PracticeSubscription
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


class ProfileSettingsView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/profile_settings.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and is_client_user(request.user):
            from django.shortcuts import redirect

            return redirect("portal:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        practice = get_practice_for_user(self.request.user)
        subscription = getattr(practice, "subscription", None) if practice else None
        context.update({
            "practice": practice,
            "subscription": subscription,
            "profile_role_label": self.request.user.nuvia_profile.get_role_display() if hasattr(self.request.user, "nuvia_profile") else "Not assigned",
        })
        return context


class PracticeSignupView(FormView):
    form_class = PracticeSignupForm
    template_name = "accounts/signup.html"
    default_plan = PracticeSubscription.Plan.SOLO
    default_period = PracticeSubscription.BillingPeriod.MONTHLY

    def get_plan_period(self):
        plan = self.request.POST.get("plan") or self.request.GET.get("plan") or self.default_plan
        period = self.request.POST.get("period") or self.request.GET.get("period") or self.default_period
        if plan not in PracticeSubscription.Plan.values:
            plan = self.default_plan
        if period not in PracticeSubscription.BillingPeriod.values:
            period = self.default_period
        return plan, period

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            from django.shortcuts import redirect

            if is_client_user(request.user):
                return redirect("portal:dashboard")
            plan, period = self.get_plan_period()
            return redirect("billing:subscribe", plan=plan, period=period)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plan, period = self.get_plan_period()
        context["selected_plan"] = plan
        context["selected_period"] = period
        context["selected_plan_label"] = PracticeSubscription.Plan(plan).label
        context["selected_period_label"] = PracticeSubscription.BillingPeriod(period).label
        return context

    def get_success_url(self):
        plan, period = self.get_plan_period()
        return reverse("billing:subscribe", kwargs={"plan": plan, "period": period})

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)
