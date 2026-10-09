import logging
import smtplib
from email.message import EmailMessage

from ..config import get_settings

log = logging.getLogger(__name__)


def email_enabled() -> bool:
    s = get_settings()
    return bool(s.smtp_host and s.admin_email)


def send_admin_email(subject: str, body: str) -> bool:
    """Envía un email al admin. Nunca lanza: un fallo de correo no debe romper la app."""
    s = get_settings()
    if not email_enabled():
        log.info("Email desactivado; se omite: %s", subject)
        return False
    msg = EmailMessage()
    msg["Subject"] = f"[Ancares Seguidores] {subject}"
    msg["From"] = s.smtp_from or s.smtp_user or s.admin_email
    msg["To"] = s.admin_email
    msg.set_content(body)
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as smtp:
            if s.smtp_starttls:
                smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password or "")
            smtp.send_message(msg)
        return True
    except Exception:  # noqa: BLE001
        log.exception("No se pudo enviar el email: %s", subject)
        return False
