"""Qidiruv yordamchilari — IG shortcode ajratish va slug generatsiya (TZ 7.5 / 8-bo'lim)."""
import re
import unicodedata

# Instagram post/reel/tv URL'idan shortcode ajratish.
# Namuna: https://www.instagram.com/p/Cabc123_-/  -> Cabc123_-
_SHORTCODE_RE = re.compile(
    r"instagram\.com/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)", re.IGNORECASE
)

_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


def extract_shortcode(value: str) -> str | None:
    """IG URL'dan shortcode qaytaradi; URL bo'lmasa None.

    Faqat shortcode berilgan bo'lsa (URL emas) — o'zini qaytaradi.
    """
    if not value:
        return None
    match = _SHORTCODE_RE.search(value)
    if match:
        return match.group(1)
    # URL emas, lekin toza shortcode ko'rinishida bo'lsa (harf/raqam/_/-)
    stripped = value.strip()
    if "/" not in stripped and " " not in stripped and re.fullmatch(r"[A-Za-z0-9_-]+", stripped):
        return stripped
    return None


def is_instagram_url(value: str) -> bool:
    return bool(value) and "instagram.com/" in value.lower()


def slugify(value: str) -> str:
    """Oddiy slug — ASCII'ga tushiradi, bo'sh joy/belgilarni '-' bilan almashtiradi."""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_str = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = _SLUG_STRIP_RE.sub("-", ascii_str).strip("-")
    return slug or "item"
