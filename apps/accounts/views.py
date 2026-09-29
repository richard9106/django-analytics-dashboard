from datetime import datetime, timezone as dt_timezone

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.crypto import get_random_string
from django.views.generic import FormView, TemplateView
from django.views import View
from django.views.generic.edit import FormView

from .access import get_practice_for_user, is_client_user, must_change_password
from apps.audit.models import AuditLog
from apps.audit.utils import log_audit_event
from apps.billing.models import PracticeSubscription
from apps.practices.google_oauth import send_gmail_message
from apps.appointments.reminders import get_gmail_integration
from .forms import EmailAuthenticationForm, ForcePasswordChangeForm, PracticeSignupForm, ProfileDetailsForm, TeamMemberCreateForm
from .models import UserProfile


def send_team_invitation(request, user, temporary_password):
    practice = user.nuvia_profile.practice
    integration = get_gmail_integration(practice)
    subject = "Your NuviaMy team invitation"
    body = (
        f"Hello {user.first_name or user.email},\n\n"
        f"You have been invited to join {practice.name} on NuviaMy.\n\n"
        f"Sign in at: {request.build_absolute_uri('/login/')}\n"
        f"Email: {user.email}\n"
        f"Temporary password: {temporary_password}\n\n"
        "You will be required to change this password when you first sign in."
    )
    if integration:
        send_gmail_message(integration, user.email, subject, body)
        return "connected Gmail"
    if send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False):
        return "email"
    return ""


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

    def get_success_url(self):
        return reverse_lazy("portal:dashboard") if is_client_user(self.request.user) else reverse_lazy("dashboard")

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


class ProfileSettingsView(LoginRequiredMixin, FormView):
    template_name = "accounts/profile_settings.html"
    form_class = ProfileDetailsForm
    success_url = reverse_lazy("profile_settings")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, 'Profile details updated. Gmail and Stripe connections were not changed.')
        return super().form_valid(form)

    def get_subscription_invoices(self, subscription):
        if not subscription or not subscription.stripe_customer_id or not settings.STRIPE_SECRET_KEY:
            return [], False
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            invoices = stripe.Invoice.list(customer=subscription.stripe_customer_id, limit=10)
        except stripe.error.StripeError:
            return [], True
        return [
            {
                "number": invoice.get("number") or invoice.get("id", "Invoice"),
                "status": invoice.get("status", "unknown").title(),
                "amount": f"{invoice.get('currency', 'usd').upper()} {(invoice.get('amount_paid') or invoice.get('amount_due') or 0) / 100:,.2f}",
                "created_at": datetime.fromtimestamp(invoice.get("created", 0), tz=dt_timezone.utc) if invoice.get("created") else None,
                "hosted_invoice_url": invoice.get("hosted_invoice_url", ""),
                "invoice_pdf": invoice.get("invoice_pdf", ""),
            }
            for invoice in invoices.get("data", [])
        ], False

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and is_client_user(request.user):
            from django.shortcuts import redirect

            return redirect("portal:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        practice = get_practice_for_user(self.request.user)
        subscription = getattr(practice, "subscription", None) if practice else None
        google_integration = practice.external_integrations.filter(provider='google').first() if practice else None
        subscription_invoices, subscription_invoice_error = self.get_subscription_invoices(subscription)
        context.update({
            "practice": practice,
            "profile_form": self.get_form(),
            "google_integration": google_integration,
            "can_manage_client_payments": bool(
                hasattr(self.request.user, "nuvia_profile")
                and self.request.user.nuvia_profile.role in {"owner", "admin"}
            ),
            "subscription": subscription,
            "subscription_invoices": subscription_invoices,
            "subscription_invoice_error": subscription_invoice_error,
            "subscription_plan_options": [
                {
                    "plan": plan,
                    "period": period,
                    "label": PracticeSubscription.Plan(plan).label,
                    "period_label": PracticeSubscription.BillingPeriod(period).label,
                    "limit": PracticeSubscription.internal_user_limit_for_plan(plan),
                    "is_current": bool(subscription and subscription.plan == plan and subscription.billing_period == period),
                }
                for plan in PracticeSubscription.Plan.values
                for period in PracticeSubscription.BillingPeriod.values
            ],
            "profile_role_label": self.request.user.nuvia_profile.get_role_display() if hasattr(self.request.user, "nuvia_profile") else "Not assigned",
        })
        return context


class TeamManagementView(LoginRequiredMixin, FormView):
    form_class = TeamMemberCreateForm
    template_name = "accounts/team.html"
    success_url = reverse_lazy("team_management")

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if request.user.is_authenticated and is_client_user(request.user):
            from django.shortcuts import redirect

            return redirect("portal:dashboard")
        practice = get_practice_for_user(request.user)
        profile = getattr(request.user, "nuvia_profile", None)
        if not practice or not profile or profile.role not in {UserProfile.Role.OWNER, UserProfile.Role.ADMIN}:
            raise PermissionDenied("Only practice owners and admins can manage team members.")
        return super().dispatch(request, *args, **kwargs)

    def get_practice(self):
        return get_practice_for_user(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["practice"] = self.get_practice()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        practice = self.get_practice()
        subscription = getattr(practice, "subscription", None) if practice else None
        context.update({
            "practice": practice,
            "subscription": subscription,
            "team_members": practice.user_profiles.exclude(role=UserProfile.Role.CLIENT).select_related("user", "user__therapist_profile") if practice else [],
            "can_add_team_member": not subscription or subscription.can_add_internal_user(),
            "gmail_connected": bool(practice and get_gmail_integration(practice)),
            "profile_role_label": self.request.user.nuvia_profile.get_role_display() if hasattr(self.request.user, "nuvia_profile") else "Not assigned",
        })
        return context

    def form_valid(self, form):
        user = form.save()
        member_name = user.get_full_name() or user.email
        if form.cleaned_data.get("send_invitation_email"):
            try:
                sent_via = send_team_invitation(self.request, user, form.temporary_password)
            except Exception:
                sent_via = ""
            if sent_via:
                messages.success(self.request, f"Team member {member_name} was created and the temporary password was sent via {sent_via} to {user.email}.")
            else:
                messages.warning(self.request, f"Team member {member_name} was created, but the email could not be sent. Temporary password: {form.temporary_password}")
        else:
            messages.success(self.request, f"Team member {member_name} was created. Temporary password: {form.temporary_password}")
        log_audit_event(
            self.request,
            AuditLog.Action.CREATE,
            "accounts.UserProfile",
            user.nuvia_profile.pk,
            practice=user.nuvia_profile.practice,
            metadata={"user_id": user.pk, "role": user.nuvia_profile.role},
        )
        return super().form_valid(form)


class TeamMemberActionView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        profile = getattr(request.user, "nuvia_profile", None)
        if is_client_user(request.user) or not profile or profile.role not in {UserProfile.Role.OWNER, UserProfile.Role.ADMIN}:
            raise PermissionDenied("Only practice owners and admins can manage team members.")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        practice = get_practice_for_user(request.user)
        target = get_object_or_404(UserProfile.objects.select_related("user"), pk=kwargs["pk"], practice=practice)
        action = request.POST.get("action")
        if action == "delete":
            if target.role == UserProfile.Role.OWNER:
                messages.error(request, "Practice owners cannot be deleted from Team Management.")
                return redirect("team_management")
            if target.user_id == request.user.pk:
                messages.error(request, "You cannot delete your own account.")
                return redirect("team_management")
            if target.user.is_active:
                messages.error(request, "Deactivate the team member before deleting the account permanently.")
                return redirect("team_management")
            member_name = target.user.get_full_name() or target.user.email
            try:
                target.user.delete()
            except ProtectedError:
                messages.error(request, "This member has related records and cannot be deleted. Keep the account deactivated instead.")
                return redirect("team_management")
            messages.success(request, f"{member_name} was permanently deleted.")
            return redirect("team_management")
        if target.role == UserProfile.Role.OWNER and action == "deactivate":
            owner_count = practice.user_profiles.filter(role=UserProfile.Role.OWNER, user__is_active=True).count()
            if owner_count <= 1:
                messages.error(request, "The practice must keep at least one active owner.")
                return redirect("team_management")
        if target.pk == request.user.nuvia_profile.pk and action == "deactivate":
            messages.error(request, "You cannot deactivate your own account.")
            return redirect("team_management")
        if action == "deactivate":
            target.user.is_active = False
            target.user.save(update_fields=["is_active"])
            messages.success(request, f"{target.user.get_full_name() or target.user.email} was deactivated.")
        elif action == "reactivate":
            subscription = getattr(practice, "subscription", None)
            if subscription and not subscription.can_add_internal_user(exclude_profile_id=target.pk):
                messages.error(request, "There are no available internal seats on the current plan.")
                return redirect("team_management")
            target.user.is_active = True
            target.user.save(update_fields=["is_active"])
            messages.success(request, f"{target.user.get_full_name() or target.user.email} was reactivated.")
        elif action == "resend_invitation":
            password = get_random_string(14)
            target.user.set_password(password)
            target.user.save(update_fields=["password"])
            target.must_change_password = True
            target.save(update_fields=["must_change_password", "updated_at"])
            try:
                sent_via = send_team_invitation(request, target.user, password)
            except Exception:
                sent_via = ""
            if sent_via:
                messages.success(request, f"A new temporary password was sent via {sent_via} to {target.user.email}.")
            else:
                messages.warning(request, f"The invitation email could not be sent. New temporary password: {password}")
        else:
            messages.error(request, "Unknown team action.")
        return redirect("team_management")


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
