import hashlib
import ipaddress
from datetime import timedelta

from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone

from apps.accounts.models import RateLimitBucket


class PostRateLimitMixin:
    """Atomic fixed-window limits shared by all workers through PostgreSQL."""
    rate_limit_scope = 'public'
    rate_limit_count = 5
    rate_limit_seconds = 3600

    def get_client_ip(self):
        # Production is reachable only via host Nginx. Use the rightmost address
        # it appends, never a client-controlled prefix in X-Forwarded-For.
        forwarded = self.request.META.get('HTTP_X_FORWARDED_FOR', '')
        candidate = forwarded.rsplit(',', 1)[-1].strip() if forwarded else self.request.META.get('REMOTE_ADDR', '')
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            return 'unknown'

    @transaction.atomic
    def is_rate_limited(self):
        now = timezone.now()
        key = hashlib.sha256(f'{self.rate_limit_scope}:{self.get_client_ip()}'.encode()).hexdigest()
        RateLimitBucket.objects.get_or_create(key=key, defaults={'expires_at': now + timedelta(seconds=self.rate_limit_seconds)})
        bucket = RateLimitBucket.objects.select_for_update().get(key=key)
        if bucket.expires_at <= now:
            bucket.attempts = 0
            bucket.expires_at = now + timedelta(seconds=self.rate_limit_seconds)
        bucket.attempts = min(bucket.attempts + 1, self.rate_limit_count + 1)
        bucket.save(update_fields=['attempts', 'expires_at'])
        return bucket.attempts > self.rate_limit_count

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'POST' and self.is_rate_limited():
            response = HttpResponse('Too many requests. Please try again later.', status=429)
            response['Retry-After'] = str(self.rate_limit_seconds)
            return response
        return super().dispatch(request, *args, **kwargs)
