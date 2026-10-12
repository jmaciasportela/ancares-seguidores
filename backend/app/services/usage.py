"""Uso anónimo de la app: cuántos dispositivos la usan, si está instalada y con qué frecuencia.

Privacidad: el móvil genera un identificador aleatorio que solo vive en su
almacenamiento local; aquí se guarda su hash. No se guardan IPs, nombres ni
nada que identifique a una persona, y los datos de más de 180 días se borran.
"""
import hashlib
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..models import Device, DeviceDay

TZ = ZoneInfo("Europe/Madrid")
SESSION_GAP = timedelta(minutes=30)  # avisos más seguidos cuentan como la misma visita
RETENTION = timedelta(days=180)
PLATFORMS = ("ios", "android", "desktop", "otro")

# Frecuencia: días distintos con uso en los últimos 30 días
FREQUENCY_BUCKETS = [(1, 1, "1 día"), (2, 3, "2–3 días"), (4, 7, "4–7 días"), (8, 14, "8–14 días"), (15, 31, "15 o más")]


def device_key(raw_id: str) -> str:
    return hashlib.sha256(raw_id.strip().lower().encode()).hexdigest()


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def local_day(dt: datetime) -> date:
    return _aware(dt).astimezone(TZ).date()


def record_ping(session: Session, raw_id: str, installed: bool, platform: str, version: Optional[str],
                now: Optional[datetime] = None) -> Device:
    now = now or datetime.now(timezone.utc)
    key = device_key(raw_id)
    device = session.scalars(select(Device).where(Device.key == key)).first()
    if device is None:
        device = Device(key=key, first_seen=now, last_seen=now, visits=1)
        session.add(device)
        session.flush()
    else:
        if now - _aware(device.last_seen) >= SESSION_GAP:
            device.visits += 1
        device.last_seen = now
    device.installed = installed
    device.platform = platform if platform in PLATFORMS else "otro"
    device.version = (version or "")[:20] or None
    today = local_day(now)
    exists = session.scalars(select(DeviceDay.id).where(DeviceDay.device_id == device.id, DeviceDay.day == today)).first()
    if not exists:
        session.add(DeviceDay(device_id=device.id, day=today))
    session.commit()
    return device


def purge_old(session: Session, now: Optional[datetime] = None) -> int:
    now = now or datetime.now(timezone.utc)
    limit = now - RETENTION
    session.execute(delete(DeviceDay).where(DeviceDay.day < local_day(limit)))
    gone = session.execute(delete(Device).where(Device.last_seen < limit)).rowcount
    session.commit()
    return gone or 0


def summary(session: Session, now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    today = local_day(now)
    since30 = today - timedelta(days=29)

    rows = session.execute(
        select(DeviceDay.device_id, DeviceDay.day).where(DeviceDay.day >= since30)
    ).all()
    days_by_device: dict = {}
    per_day = Counter()
    for device_id, day in rows:
        days_by_device.setdefault(device_id, set()).add(day)
        per_day[day] += 1

    def active_since(days: int) -> set:
        start = today - timedelta(days=days - 1)
        return {d for d, ds in days_by_device.items() if any(x >= start for x in ds)}

    active30 = active_since(30)
    devices = {d.id: d for d in session.scalars(select(Device).where(Device.id.in_(active30))).all()} if active30 else {}
    installed30 = [d for d in devices.values() if d.installed]
    new7 = session.scalar(select(func.count()).select_from(Device).where(Device.first_seen >= now - timedelta(days=7))) or 0

    frequency = []
    for lo, hi, label in FREQUENCY_BUCKETS:
        n = sum(1 for d in active30 if lo <= len(days_by_device[d]) <= hi)
        frequency.append({"label": label, "devices": n})
    total_days = sum(len(days_by_device[d]) for d in active30)

    return {
        "active_today": len(active_since(1)),
        "active_7d": len(active_since(7)),
        "active_30d": len(active30),
        "installed_30d": len(installed30),
        "installed_7d": sum(1 for d in installed30 if d.id in active_since(7)),
        "new_7d": new7,
        "total_devices": session.scalar(select(func.count()).select_from(Device)) or 0,
        # Días de uso a la semana de media entre los activos del mes
        "days_per_week": round(total_days / len(active30) * 7 / 30, 1) if active30 else None,
        "daily": [
            {"day": (since30 + timedelta(days=i)).isoformat(), "devices": per_day.get(since30 + timedelta(days=i), 0)}
            for i in range(30)
        ],
        "frequency": frequency,
        "platforms": dict(Counter(d.platform for d in devices.values())),
        "versions": dict(Counter(d.version or "?" for d in devices.values()).most_common(6)),
    }
