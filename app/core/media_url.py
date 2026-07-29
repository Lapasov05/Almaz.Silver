"""Media URL normalizatori — mijozga (IG/TG) yuboriladigan rasm URL'ini tashqi (public) qiladi.

Muammo (bug): rasm yuklashда URL `PUBLIC_BASE_URL` bilan qotib qoladi. Agar u
`http://localhost:8000` (yoki `http://api:8000` / `http://minio:9000` kabi ichki host) bo'lsa,
Telegram/Instagram serverlari o'zi shu URL'ni ochib rasmni ololmaydi — rasm "urli ketib" ko'rinmaydi.

Yechim: YUBORISH vaqtida URL joriy `settings.public_base_url` bo'yicha qayta quriladi. Shunda
eski (localhost bilan qotgan) yozuvlar ham to'g'ri host bilan ketadi — PUBLIC_BASE_URL to'g'ri
(public https domen) qo'yilsa yetarli. Nisbiy (`/uploads/...`) URL ham to'liq qilinadi.
"""
from urllib.parse import urlsplit, urlunsplit

from app.core.config import get_settings

settings = get_settings()

# Tashqaridan ochilmaydigan ichki hostlar — bularni public_base_url bilan almashtiramiz
_INTERNAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "api", "minio", "nginx", "web"}


def public_media_url(url: str | None) -> str:
    """Rasm URL'ini tashqi (public) bazaga keltiradi. Bo'sh bo'lsa "" qaytadi.

    - Nisbiy URL (`/uploads/x.jpg`) → `{public_base_url}/uploads/x.jpg`.
    - Ichki host (localhost/api/minio/...) bo'lgan absolute URL → path saqlanib, host public bazaga.
    - Allaqachon tashqi https domen bo'lsa — tegilmaydi.
    """
    if not url:
        return ""
    url = url.strip()
    base = settings.public_base_url.rstrip("/")

    # Nisbiy yo'l — to'g'ridan-to'g'ri public bazaga ulaymiz
    if url.startswith("/"):
        return f"{base}{url}"

    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        # sxema/host yo'q (masalan "uploads/x.jpg") — nisbiy deb qaraymiz
        return f"{base}/{url.lstrip('/')}"

    host = parts.hostname or ""
    if host.lower() in _INTERNAL_HOSTS:
        # Ichki host — path (va query)ni saqlab, public bazaga qayta quramiz
        base_parts = urlsplit(base)
        return urlunsplit(
            (base_parts.scheme, base_parts.netloc, parts.path, parts.query, "")
        )
    # Tashqi domen — o'zgartirmaymiz
    return url
