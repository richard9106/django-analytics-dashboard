import hashlib
import json
import secrets
import time
import uuid
from datetime import timedelta

import pyotp
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from apps.practices.fields import get_fernet
from .access import is_client_user
from .models import AccountSecurity


def requires_mfa(user):
    return settings.MFA_REQUIRED and (user.is_staff or user.is_superuser or not is_client_user(user))


def security_state(user):
    return AccountSecurity.objects.get_or_create(user=user)[0]


def verified(request, state):
    return state.confirmed and request.session.get('mfa_version') == str(state.session_version)


def safe_next(request, candidate=None):
    target = candidate or request.session.get('security_next', '')
    if target and url_has_allowed_host_and_scheme(target, {request.get_host()}, require_https=request.is_secure()):
        # Only local relative targets; never redirect back into the auth flow.
        if target.startswith('/') and not target.startswith('//') and not target.startswith(('/login/', '/accounts/security/', '/logout/')):
            return target
    return '/portal/' if is_client_user(request.user) else '/dashboard/'


def establish_session(request, state, mfa=False):
    request.session.cycle_key()
    request.session['security_version'] = str(state.session_version)
    request.session['security_auth_at'] = time.time()
    if mfa:
        request.session['mfa_version'] = str(state.session_version)


def new_recovery_codes(state):
    codes = [secrets.token_hex(16) for _ in range(10)]
    state.recovery_hashes = [hashlib.sha256(code.encode()).hexdigest() for code in codes]
    return ['-'.join(code[i:i + 8] for i in range(0, 32, 8)) for code in codes]


def encrypt_session_value(value):
    return get_fernet().encrypt(json.dumps(value).encode()).decode()


def decrypt_session_value(value):
    return json.loads(get_fernet().decrypt(value.encode()).decode())


def matching_counter(secret, code, last_counter=-1):
    if len(code) != 6 or not code.isascii() or not code.isdigit():
        return None
    totp = pyotp.TOTP(secret)
    current = int(time.time()) // totp.interval
    for counter in (current, current - 1, current + 1):
        if counter > last_counter and pyotp.utils.strings_equal(totp.at(counter * totp.interval), code):
            return counter
    return None


def record_failure(state):
    state.failed_attempts += 1
    if state.failed_attempts >= 5:
        state.blocked_until = timezone.now() + timedelta(minutes=15)
    state.save(update_fields=['failed_attempts', 'blocked_until'])


def clear_expired_lock(state):
    if state.blocked_until and state.blocked_until <= timezone.now():
        state.failed_attempts = 0
        state.blocked_until = None


@transaction.atomic
def verify_factor(user, code, password=None):
    state = AccountSecurity.objects.select_for_update().get(user=user)
    clear_expired_lock(state)
    if not state.confirmed or (state.blocked_until and state.blocked_until > timezone.now()):
        return False
    user.refresh_from_db(fields=['password', 'is_active'])
    if not user.is_active or (password is not None and not user.check_password(password)):
        record_failure(state)
        return False
    normalized = code.replace('-', '').replace(' ', '')
    counter = matching_counter(state.secret, normalized, state.last_counter)
    digest = hashlib.sha256(normalized.encode()).hexdigest()
    recovery_index = next((i for i, value in enumerate(state.recovery_hashes) if secrets.compare_digest(value, digest)), None)
    if counter is None and recovery_index is None:
        record_failure(state)
        return False
    if counter is not None:
        state.last_counter = counter
    else:
        state.recovery_hashes.pop(recovery_index)
    state.failed_attempts = 0
    state.blocked_until = None
    state.save()
    return state


@transaction.atomic
def confirm_enrollment(user, secret, code, password, version, replace=False):
    state = AccountSecurity.objects.select_for_update().get(user=user)
    clear_expired_lock(state)
    if str(state.session_version) != version or (state.confirmed and not replace):
        return None
    if state.blocked_until and state.blocked_until > timezone.now():
        return None
    user.refresh_from_db(fields=['password', 'is_active'])
    counter = matching_counter(secret, code)
    if not user.is_active or not user.check_password(password) or counter is None:
        record_failure(state)
        return None
    state.secret = secret
    state.confirmed = True
    state.last_counter = counter
    state.failed_attempts = 0
    state.blocked_until = None
    state.session_version = uuid.uuid4()
    codes = new_recovery_codes(state)
    state.save()
    return codes, state
