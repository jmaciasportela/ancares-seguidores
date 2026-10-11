import logging
import smtplib
import socket
from email.message import EmailMessage
from typing import List, Optional, Tuple

from ..config import get_settings

log = logging.getLogger(__name__)


def missing_settings() -> List[str]:
    s = get_settings()
    return [name for name, value in (("SMTP_HOST", s.smtp_host), ("ADMIN_EMAIL", s.admin_email)) if not (value or "").strip()]


def email_enabled() -> bool:
    return not missing_settings()


def use_ssl() -> bool:
    """SSL directo (puerto 465) o STARTTLS (587). SMTP_SSL lo fuerza; si no, se deduce del puerto."""
    s = get_settings()
    return s.smtp_ssl if s.smtp_ssl is not None else s.smtp_port == 465


def email_status() -> dict:
    s = get_settings()
    return {
        "enabled": email_enabled(),
        "missing": missing_settings(),
        "to": s.admin_email or None,
        "host": s.smtp_host or None,
        "port": s.smtp_port,
        "security": "SSL" if use_ssl() else ("STARTTLS" if s.smtp_starttls else "ninguna"),
    }


def _send(subject: str, body: str) -> None:
    """Envía el email o lanza la excepción del servidor SMTP."""
    s = get_settings()
    msg = EmailMessage()
    msg["Subject"] = f"[Ancares Seguidores] {subject}"
    msg["From"] = s.smtp_from or s.smtp_user or s.admin_email
    msg["To"] = s.admin_email
    msg.set_content(body)
    if use_ssl():
        smtp = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=20)
    else:
        smtp = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20)
    with smtp:
        if not use_ssl() and s.smtp_starttls:
            smtp.starttls()
        if s.smtp_user:
            smtp.login(s.smtp_user, s.smtp_password or "")
        smtp.send_message(msg)


def explain(exc: Exception) -> str:
    """Mensaje comprensible para los fallos más habituales."""
    s = get_settings()
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return ("El servidor rechazó el usuario o la contraseña. Con Gmail hace falta una «contraseña de "
                "aplicación» (con la verificación en dos pasos activada), no la contraseña normal.")
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return (f"Sin respuesta de {s.smtp_host}:{s.smtp_port}. Puede que tu proveedor del VPS bloquee ese "
                "puerto de salida (algunos bloquean 25 y 465): prueba con 587.")
    if isinstance(exc, ConnectionRefusedError):
        return f"{s.smtp_host}:{s.smtp_port} rechazó la conexión: revisa SMTP_HOST y SMTP_PORT."
    if isinstance(exc, socket.gaierror):
        return f"No se encuentra el servidor «{s.smtp_host}»: revisa SMTP_HOST."
    if isinstance(exc, smtplib.SMTPServerDisconnected):
        return ("El servidor cortó la conexión. Si usas el puerto 465 necesitas SSL (se activa solo con ese "
                "puerto o con SMTP_SSL=true); con 587, STARTTLS.")
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return "El servidor no acepta el remitente: pon en SMTP_FROM la misma dirección que SMTP_USER."
    return f"{type(exc).__name__}: {exc}"


def send_admin_email(subject: str, body: str) -> bool:
    """Envía un email al admin. Nunca lanza: un fallo de correo no debe romper la app."""
    if not email_enabled():
        log.warning("Email desactivado (falta %s); se omite: %s", ", ".join(missing_settings()), subject)
        return False
    try:
        _send(subject, body)
        log.info("Email enviado: %s", subject)
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("No se pudo enviar el email «%s»: %s", subject, explain(exc))
        return False


def send_test_email() -> Tuple[bool, Optional[str]]:
    if not email_enabled():
        return False, f"Falta configurar en el .env: {', '.join(missing_settings())}"
    try:
        _send("Email de prueba", "Si lees esto, los avisos por email de Ancares Seguidores funcionan. 🏐")
        return True, None
    except Exception as exc:  # noqa: BLE001
        log.error("Falló el email de prueba: %s", explain(exc))
        return False, explain(exc)
