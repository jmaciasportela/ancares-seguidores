from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    db_path: Path = BASE_DIR.parent / "data" / "ancares.db"
    static_dir: Path = BASE_DIR.parent / "frontend" / "dist"

    admin_password: str = "cambiame"
    secret_key: str = "dev-secret-cambiame"
    cookie_secure: bool = False
    session_max_age: int = 60 * 60 * 24 * 30

    # Sincronización diaria: "minuto hora * * *" en Europe/Madrid
    sync_cron: str = "0 7 * * *"
    sync_enabled: bool = True
    timezone: str = "Europe/Madrid"
    user_agent: str = "AncaresSeguidores/1.0 (app no oficial de seguidores; contacto en la app)"
    team_keyword: str = "ancares"

    # Email (feedback y avisos de sincronización). Vacío = desactivado.
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_starttls: bool = True
    smtp_from: Optional[str] = None
    admin_email: Optional[str] = None
    public_url: str = "http://localhost:8000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
