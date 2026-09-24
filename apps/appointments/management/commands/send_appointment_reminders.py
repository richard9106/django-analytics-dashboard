from django.core.management.base import BaseCommand

from apps.appointments.reminders import due_reminder_appointments, send_appointment_reminder


class Command(BaseCommand):
    help = 'Send Gmail appointment reminders for upcoming scheduled appointments.'

    def add_arguments(self, parser):
        parser.add_argument('--window-hours', type=int, default=24)

    def handle(self, *args, **options):
        sent = 0
        failed = 0
        for appointment in due_reminder_appointments(window_hours=options['window_hours']):
            if send_appointment_reminder(appointment):
                sent += 1
            else:
                failed += 1
        self.stdout.write(self.style.SUCCESS(f'Sent {sent} reminder(s); {failed} failed.'))
