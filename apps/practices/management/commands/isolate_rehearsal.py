from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from ops.rehearsal import validate_rehearsal, clear_restored_integrations


class Command(BaseCommand):
    help='Remove OAuth credentials only from an explicitly isolated restored database.'

    def add_arguments(self,parser):
        parser.add_argument('--confirm-isolated',action='store_true')

    @transaction.atomic
    def handle(self,*args,**options):
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_database()')
            database=cursor.fetchone()[0]
        try:
            validate_rehearsal(settings,database,options['confirm_isolated'])
        except ValueError as error:
            raise CommandError(str(error))
        count=clear_restored_integrations()
        self.stdout.write(self.style.SUCCESS(f'Isolated rehearsal: {count} integration records disconnected. No provider requests sent.'))
