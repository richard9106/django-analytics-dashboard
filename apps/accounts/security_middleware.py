import time
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.cache import patch_cache_control
from django.utils.deprecation import MiddlewareMixin

from apps.rate_limit import PostRateLimitMixin
from .access import must_change_password
from .security import requires_mfa, security_state, verified


class SecuritySessionMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.method == 'POST' and request.resolver_match.view_name == 'admin:login':
            limiter = PostRateLimitMixin()
            limiter.request = request
            limiter.rate_limit_scope = 'login'
            limiter.rate_limit_count = 10
            limiter.rate_limit_seconds = 900
            if limiter.is_rate_limited():
                response = HttpResponse('Too many requests. Please try again later.', status=429)
                response['Retry-After'] = '900'
                return response
        if not request.user.is_authenticated:
            return None
        request._security_authenticated = True
        now = time.time()
        session = request.session
        state = security_state(request.user)
        request.account_security = state
        started = session.get('security_started_at', 0)
        last = session.get('security_last_activity', 0)
        if (session.get('security_version') != str(state.session_version)
                or now - started >= settings.SECURITY_ABSOLUTE_TIMEOUT
                or now - last >= settings.SECURITY_IDLE_TIMEOUT):
            logout(request)
            if request.resolver_match.view_name == 'security_session':
                return JsonResponse({'authenticated': False}, status=401)
            return redirect(reverse('login') + '?session_expired=1')
        session['security_last_activity'] = now
        name = request.resolver_match.view_name
        if name in {'login', 'logout', 'admin:login', 'admin:logout'}:
            return None
        pending_mfa = requires_mfa(request.user) and not verified(request, state)
        if pending_mfa and now - session.get('security_password_at', 0) >= settings.SECURITY_CHALLENGE_TIMEOUT:
            logout(request)
            return redirect(reverse('login') + '?session_expired=1')
        if must_change_password(request.user):
            if name == 'force_password_change' or (name == 'security_session' and not requires_mfa(request.user)):
                return None
            return redirect('force_password_change')
        if pending_mfa:
            target = 'mfa_challenge' if state.confirmed else 'mfa_setup'
            if name != target:
                if not request.path.startswith('/accounts/security/'):
                    session['security_next'] = request.path
                if name == 'security_session':
                    return JsonResponse({'authenticated': False}, status=401)
                return redirect(target)
            return None
        sensitive = name == 'practice_data_export' or (
            request.method == 'POST' and name in {'team_management', 'team_member_action', 'profile_settings'})
        if settings.MFA_REQUIRED and sensitive and now - session.get('security_auth_at', 0) >= settings.SECURITY_REAUTH_TIMEOUT:
            return redirect(reverse('security_reauthenticate') + '?' + urlencode({'next': request.path}))
        return None

    def process_response(self, request, response):
        if getattr(request, '_security_authenticated', False):
            patch_cache_control(response, no_store=True, no_cache=True, private=True, max_age=0)
            response['Referrer-Policy'] = 'no-referrer'
        if request.path.startswith('/accounts/security/'):
            response['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'self'"
        return response
