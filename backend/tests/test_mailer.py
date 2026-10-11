import smtplib

import pytest

from app.config import get_settings
from app.services import mailer


class FakeSMTP:
    """Servidor SMTP simulado: guarda lo que se envía."""

    instances = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port, self.ssl = host, port, False
        self.tls = False
        self.login_args = None
        self.sent = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.tls = True

    def login(self, user, password):
        if password == "mala":
            raise smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")
        self.login_args = (user, password)

    def send_message(self, msg):
        self.sent.append(msg)


class FakeSMTPSSL(FakeSMTP):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.ssl = True


@pytest.fixture()
def smtp(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", FakeSMTPSSL)
    s = get_settings()
    for key, value in dict(smtp_host="smtp.test", smtp_port=587, smtp_user="yo@test.es", smtp_password="buena",
                           smtp_from=None, admin_email="admin@test.es", smtp_ssl=None, smtp_starttls=True).items():
        monkeypatch.setattr(s, key, value)
    return FakeSMTP.instances


def login(client):
    assert client.post("/api/admin/login", json={"password": "secreto"}).status_code == 200


def test_not_configured(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "smtp_host", "")
    monkeypatch.setattr(get_settings(), "admin_email", None)
    login(client)
    status = client.get("/api/admin/email").json()
    assert status["enabled"] is False and status["missing"] == ["SMTP_HOST", "ADMIN_EMAIL"]
    r = client.post("/api/admin/email/test").json()
    assert r["ok"] is False and "SMTP_HOST" in r["error"]


def test_test_email_starttls(client, smtp):
    login(client)
    r = client.post("/api/admin/email/test").json()
    assert r["ok"] is True and r["security"] == "STARTTLS"
    conn = smtp[-1]
    assert (conn.host, conn.port, conn.tls, conn.ssl) == ("smtp.test", 587, True, False)
    assert conn.login_args == ("yo@test.es", "buena")
    assert conn.sent[0]["To"] == "admin@test.es" and "prueba" in conn.sent[0]["Subject"]


def test_ssl_on_port_465(client, smtp, monkeypatch):
    monkeypatch.setattr(get_settings(), "smtp_port", 465)
    login(client)
    assert client.post("/api/admin/email/test").json()["security"] == "SSL"
    assert smtp[-1].ssl is True and smtp[-1].tls is False


def test_bad_password_is_explained(client, smtp, monkeypatch):
    monkeypatch.setattr(get_settings(), "smtp_password", "mala")
    login(client)
    r = client.post("/api/admin/email/test").json()
    assert r["ok"] is False and "contraseña de aplicación" in r["error"]


def test_feedback_sends_email(client, smtp):
    r = client.post("/api/feedback", json={"kind": "error", "message": "No carga el calendario", "name": "Luis"})
    assert r.status_code == 201
    sent = [m for conn in smtp for m in conn.sent]
    assert len(sent) == 1
    assert "Nuevo feedback" in sent[0]["Subject"] and "No carga el calendario" in sent[0].get_content()
