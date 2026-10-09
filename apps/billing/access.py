from datetime import timedelta

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from django.views.generic.edit import CreateView, UpdateView, DeleteView

from apps.accounts.access import get_practice_for_user, is_client_user
from apps.accounts.models import UserProfile
from .models import PracticeSubscription


def subscription_access(practice):
    """Legacy/internal workspaces opt in; every public signup requires activation."""
    if not practice or not practice.subscription_required:
        return {'mode': 'full'}
    sub = getattr(practice, 'subscription', None)
    # Local trials never create a Stripe customer or payment commitment.
    # An existing paid subscription always governs access, including cancellation.
    if not sub or not sub.stripe_subscription_id:
        if practice.free_trial_ends_at:
            if timezone.now() < practice.free_trial_ends_at:
                return {'mode': 'full', 'free_access': practice.free_access_kind, 'until': practice.free_trial_ends_at}
            return {'mode': 'readonly', 'free_access': practice.free_access_kind, 'until': practice.free_trial_ends_at}
    if not sub:
        return {'mode': 'pending'}
    if sub.status in {PracticeSubscription.Status.ACTIVE, PracticeSubscription.Status.TRIALING}:
        return {'mode': 'full'}
    if sub.status == PracticeSubscription.Status.PAST_DUE and sub.payment_failed_at:
        until = sub.payment_failed_at + timedelta(days=7)
        if timezone.now() < until:
            return {'mode': 'grace', 'until': until}
    if sub.status in {PracticeSubscription.Status.INCOMPLETE, 'incomplete_expired'}:
        return {'mode': 'pending'}
    return {'mode': 'readonly'}


class SubscriptionAccessMiddleware(MiddlewareMixin):
    always_available = {
        'home', 'pricing', 'features', 'help_center', 'support_contact', 'cookie_policy', 'privacy_policy',
        'login', 'logout', 'force_password_change', 'profile_settings', 'practice_data_export',
        'billing:subscription_access', 'billing:subscribe', 'billing:subscribe_success',
        'billing:subscribe_cancel', 'billing:customer_portal', 'billing:change_plan',
        'billing:plan_preview', 'billing:stripe_webhook', 'signup',
    }
    # These GET endpoints can initiate external connections, rather than just read records.
    mutating_gets = {'practice_settings:google_connect', 'practice_settings:google_callback',
                     'practice_settings:stripe_connect', 'practice_settings:stripe_connect_return'}

    def process_view(self, request, view_func, view_args, view_kwargs):
        name = request.resolver_match.view_name
        practice = None
        if request.user.is_authenticated:
            practice = get_practice_for_user(request.user)
            if not practice:
                access = getattr(request.user, 'client_portal_access', None)
                practice = access.practice if access else None
        elif name == 'public_booking':
            from apps.practices.models import Practice
            practice = Practice.objects.filter(public_booking_slug=view_kwargs.get('slug')).first()
        state = subscription_access(practice)
        request.subscription_access = state
        request.subscription_manager = bool(
            request.user.is_authenticated and not is_client_user(request.user)
            and getattr(getattr(request.user, 'nuvia_profile', None), 'role', None)
            in {UserProfile.Role.OWNER, UserProfile.Role.ADMIN})
        if state['mode'] in {'full', 'grace'}:
            return None
        if name in self.always_available or name.startswith(('security_', 'mfa_', 'password_reset')):
            return None
        if name.startswith('admin:') and request.user.is_superuser:
            return None
        if state['mode'] == 'readonly' and request.method in {'GET', 'HEAD', 'OPTIONS'}:
            cls = getattr(view_func, 'view_class', None)
            if name not in self.mutating_gets and not (cls and issubclass(cls, (CreateView, UpdateView, DeleteView))):
                return None
        request._audit_denied_reason = 'subscription_' + state['mode']
        if name == 'public_booking':
            return render(request, 'billing/booking_unavailable.html', status=403)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', ''):
            return JsonResponse({'error': 'subscription_required', 'mode': state['mode']}, status=403)
        return redirect('billing:subscription_access')
