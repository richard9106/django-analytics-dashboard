from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import RateLimitBucket


class Command(BaseCommand):
    help = 'Remove expired, hashed-IP security rate-limit buckets.'

    def handle(self, *args, **options):
        count, _ = RateLimitBucket.objects.filter(expires_at__lte=timezone.now()).delete()
        self.stdout.write(f'Removed {count} expired security rate-limit buckets.')
