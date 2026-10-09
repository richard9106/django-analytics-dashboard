import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlencode
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.urls import reverse
from apps.practices.models import EarlyAccessInvitation

class Command(BaseCommand):
    help = 'Issue one of ten private, email-bound invitations. Prints a private link; sends no email.'

    def add_arguments(self, parser):
        parser.add_argument('slot', type=int)
        parser.add_argument('email')

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            validate_email(options['email'])
        except ValidationError as error:
            raise CommandError('Enter a valid email address.') from error
        if not 1 <= options['slot'] <= 10:
            raise CommandError('Slot must be between 1 and 10.')
        invitation = EarlyAccessInvitation.objects.select_for_update().get(slot=options['slot'])
        if invitation.redeemed_at:
            raise CommandError('This slot was redeemed and cannot be issued again.')
        token = secrets.token_urlsafe(32)
        invitation.email = options['email'].strip().lower()
        invitation.token_hash = hashlib.sha256(token.encode()).hexdigest()
        invitation.expires_at = timezone.now() + timedelta(days=30)
        invitation.save()
        self.stdout.write('https://nuviamy.com' + reverse('signup') + '?' + urlencode({'invitation': token}))
