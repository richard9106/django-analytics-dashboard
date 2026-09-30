from django.core.cache import cache
from django.http import HttpResponse


class PostRateLimitMixin:
    """Apply a fixed-window IP limit to public POST endpoints."""

    rate_limit_scope = "public"
    rate_limit_count = 5
    rate_limit_seconds = 3600

    def get_client_ip(self):
        # Nginx is the only public entry point and supplies this header.
        forwarded_for = self.request.META.get("HTTP_X_FORWARDED_FOR", "")
        return forwarded_for.split(",", 1)[0].strip() if forwarded_for else self.request.META.get("REMOTE_ADDR", "")

    def is_rate_limited(self):
        key = f"rate-limit:{self.rate_limit_scope}:{self.get_client_ip()}"
        if cache.add(key, 1, timeout=self.rate_limit_seconds):
            return False
        return cache.incr(key) > self.rate_limit_count

    def dispatch(self, request, *args, **kwargs):
        if request.method == "POST" and self.is_rate_limited():
            return HttpResponse("Too many requests. Please try again later.", status=429)
        return super().dispatch(request, *args, **kwargs)
