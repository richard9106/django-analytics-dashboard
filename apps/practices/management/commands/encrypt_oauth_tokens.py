from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.practices.models import ExternalIntegration


class Command(BaseCommand):
    help = 'Re-saves OAuth tokens so EncryptedTextField encrypts any existing plaintext values.'

    def handle(self, *args, **options):
        if not settings.FIELD_ENCRYPTION_KEY:
            raise CommandError('FIELD_ENCRYPTION_KEY must be configured before encrypting OAuth tokens.')

        count = 0
        for integration in ExternalIntegration.objects.exclude(access_token='').iterator():
            integration.save(update_fields=['access_token', 'refresh_token', 'updated_at'])
            count += 1
        self.stdout.write(self.style.SUCCESS(f'Encrypted OAuth tokens for {count} integration(s).'))
