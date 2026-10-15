"""Operational notifications for new professional workspaces."""
import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def notify_new_signup(user):
    recipient = settings.SIGNUP_NOTIFICATION_EMAIL
    if not recipient:
        return
    practice = user.nuvia_profile.practice
    body = (
        "Se ha registrado una nueva cuenta profesional en NuviaMy.\n\n"
        f"Nombre: {user.get_full_name()}\n"
        f"Correo: {user.email}\n"
        f"Consulta: {practice.name}\n"
        f"Fecha de registro (UTC): {user.date_joined:%Y-%m-%d %H:%M}\n\n"
        "Este aviso confirma el registro, no una suscripción de pago.\n"
    )
    try:
        sent = send_mail("NuviaMy: nuevo registro", body, settings.DEFAULT_FROM_EMAIL,
                         [recipient], fail_silently=False)
        if not sent:
            logger.error("Signup notification was not sent for user_id=%s", user.pk)
    except Exception:
        # SMTP errors must not stop an otherwise successful registration.
        # Avoid logging exception details, which can contain SMTP credentials.
        logger.error("Signup notification delivery failed for user_id=%s", user.pk)
