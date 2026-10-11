"""Previsión del tiempo para la hora del partido (Open-Meteo, gratis y sin clave).

Los pabellones no traen coordenadas, así que se ubica el partido por ciudad:
se busca una localidad conocida en el pabellón y, si no, en el nombre del
equipo local ("Rio Duero Soria A"); como último recurso, la ciudad por defecto.
Es una aproximación: la app indica para qué ciudad es la previsión.
"""
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

import httpx

from ..config import get_settings
from ..parsers.common import norm

log = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_DAYS = 16
CACHE_SECONDS = 60 * 60


@dataclass(frozen=True)
class Place:
    name: str
    lat: float
    lon: float


# Localidades de Castilla y León y alrededores (coordenadas del centro urbano)
PLACES: Dict[str, Place] = {
    norm(p.name): p
    for p in [
        Place("Valladolid", 41.652, -4.724),
        Place("Burgos", 42.343, -3.696),
        Place("León", 42.599, -5.567),
        Place("Palencia", 42.009, -4.528),
        Place("Salamanca", 40.970, -5.663),
        Place("Segovia", 40.948, -4.118),
        Place("Soria", 41.764, -2.464),
        Place("Zamora", 41.503, -5.746),
        Place("Ávila", 40.656, -4.700),
        Place("Ponferrada", 42.546, -6.596),
        Place("Medina del Campo", 41.311, -4.914),
        Place("Aranda de Duero", 41.670, -3.689),
        Place("Miranda de Ebro", 42.686, -2.947),
        Place("Laguna de Duero", 41.583, -4.717),
        Place("Arroyo de la Encomienda", 41.618, -4.795),
        Place("La Cistérniga", 41.610, -4.680),
        Place("Simancas", 41.591, -4.828),
        Place("Tudela de Duero", 41.583, -4.583),
        Place("Tordesillas", 41.502, -5.000),
        Place("Íscar", 41.364, -4.534),
        Place("Cuéllar", 41.401, -4.315),
        Place("Benavente", 42.003, -5.678),
        Place("Astorga", 42.458, -6.056),
        Place("Béjar", 40.386, -5.763),
        Place("San Andrés del Rabanedo", 42.615, -5.611),
        Place("Villaquilambre", 42.643, -5.553),
        Place("Santa Marta de Tormes", 40.950, -5.627),
        Place("Villamuriel de Cerrato", 41.951, -4.516),
        Place("El Espinar", 40.719, -4.249),
        Place("Guardo", 42.789, -4.843),
        Place("Venta de Baños", 41.922, -4.494),
        Place("Peñafiel", 41.598, -4.119),
    ]
}

# Pabellones conocidos cuyo nombre no lleva la ciudad
VENUE_HINTS = {
    "fuente la mora": "Valladolid",
    "cristo rey": "Valladolid",
    "polideportivo agustinas": "Valladolid",
    "pajaritos": "Soria",
    "liceo castilla": "Burgos",
    "jose arroyo": "Ponferrada",
}

_geo_cache: Dict[str, Optional[Place]] = {}
_forecast_cache: Dict[Tuple[float, float], Tuple[float, dict]] = {}


def _find_place(text: Optional[str]) -> Optional[Place]:
    n = norm(text)
    if not n:
        return None
    for hint, city in VENUE_HINTS.items():
        if hint in n:
            return PLACES[norm(city)]
    for key in sorted(PLACES, key=len, reverse=True):
        if re.search(r"(^|\W)" + re.escape(key) + r"($|\W)", n):
            return PLACES[key]
    return None


def _geocode(name: str) -> Optional[Place]:
    key = norm(name)
    if key in _geo_cache:
        return _geo_cache[key]
    place = None
    try:
        with httpx.Client(timeout=8) as client:
            r = client.get(GEOCODE_URL, params={"name": name, "count": 1, "language": "es", "countryCode": "ES"})
            r.raise_for_status()
            hit = (r.json().get("results") or [None])[0]
            if hit:
                place = Place(hit["name"], round(hit["latitude"], 3), round(hit["longitude"], 3))
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        log.info("No se pudo geolocalizar %r: %s", name, exc)
        return None  # sin cachear: se reintentará
    _geo_cache[key] = place
    return place


def locate(venue: Optional[str], home_team: Optional[str]) -> Place:
    place = _find_place(venue) or _find_place(home_team)
    if place:
        return place
    # "Pabellón X, Localidad": lo que va tras la última coma suele ser la localidad
    if venue and "," in venue:
        place = _geocode(venue.rsplit(",", 1)[1].strip())
        if place:
            return place
    default = get_settings().weather_default_city
    return PLACES.get(norm(default)) or PLACES[norm("Valladolid")]


def _hourly(place: Place) -> dict:
    key = (place.lat, place.lon)
    cached = _forecast_cache.get(key)
    if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]
    params = {
        "latitude": place.lat,
        "longitude": place.lon,
        "hourly": "temperature_2m,precipitation_probability,weather_code,wind_speed_10m,is_day",
        "timezone": "GMT",
        "forecast_days": FORECAST_DAYS,
    }
    with httpx.Client(timeout=10) as client:
        r = client.get(FORECAST_URL, params=params)
        r.raise_for_status()
        hourly = r.json()["hourly"]
    _forecast_cache[key] = (time.monotonic(), hourly)
    return hourly


def forecast_for(starts_at: datetime, venue: Optional[str], home_team: Optional[str], now: Optional[datetime] = None) -> dict:
    """Previsión para la hora del partido, o `available: false` con el motivo."""
    now = now or datetime.now(timezone.utc)
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)
    place = locate(venue, home_team)
    base = {"available": False, "place": place.name}
    if starts_at < now - timedelta(hours=3):
        return {**base, "reason": "past"}
    horizon = now + timedelta(days=FORECAST_DAYS - 1)
    if starts_at > horizon:
        return {**base, "reason": "too_far", "available_from": (starts_at - timedelta(days=FORECAST_DAYS - 1)).date().isoformat()}
    try:
        hourly = _hourly(place)
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        log.info("Sin previsión para %s: %s", place.name, exc)
        return {**base, "reason": "error"}

    # Hora en punto más cercana al inicio (los "y media" se quedan en su hora: 10:30 -> 10:00)
    target = (starts_at + timedelta(minutes=29)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:00")
    try:
        i = hourly["time"].index(target)
    except ValueError:
        return {**base, "reason": "too_far"}
    return {
        **base,
        "available": True,
        "time": target + "Z",
        "temperature": hourly["temperature_2m"][i],
        "precipitation_probability": hourly["precipitation_probability"][i],
        "weather_code": hourly["weather_code"][i],
        "wind_speed": hourly["wind_speed_10m"][i],
        "is_day": bool(hourly["is_day"][i]),
    }
