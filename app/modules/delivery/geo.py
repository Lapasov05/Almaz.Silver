"""Geo yordamchilari — zona (Toshkent/BTS) aniqlash va eng yaqin BTS filialini topish (TZ 11)."""
import math
from decimal import Decimal

from app.core.config import get_settings

settings = get_settings()


def is_in_tashkent(lat: float, lng: float) -> bool:
    """lat/lng Toshkent shahar chegara-quti ichidami (config bounding-box)."""
    return (
        settings.delivery_tashkent_lat_min <= lat <= settings.delivery_tashkent_lat_max
        and settings.delivery_tashkent_lng_min <= lng <= settings.delivery_tashkent_lng_max
    )


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Ikki nuqta orasidagi masofa (km) — haversine formulasi."""
    r = 6371.0  # Yer radiusi (km)
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_branch(lat: float, lng: float, branches: list) -> tuple[object, float] | None:
    """Berilgan nuqtaga eng yaqin BTS filialini qaytaradi: (branch, masofa_km). Bo'sh bo'lsa None."""
    ranked = branches_by_distance(lat, lng, branches)
    return ranked[0] if ranked else None


def branches_by_distance(lat: float, lng: float, branches: list) -> list[tuple[object, float]]:
    """Filiallarni masofa bo'yicha saralab (yaqindan uzoqqa) qaytaradi: [(branch, masofa_km), ...]."""
    out = []
    for b in branches:
        if b.lat is None or b.lng is None:
            continue
        out.append((b, haversine_km(lat, lng, float(b.lat), float(b.lng))))
    out.sort(key=lambda x: x[1])
    return out


def to_float(value: Decimal | float | None) -> float | None:
    return float(value) if value is not None else None
