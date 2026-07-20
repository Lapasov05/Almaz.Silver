"""Checkout token generatsiya/hash (TZ 11/15) — token ochiq saqlanmaydi, faqat hash."""
import hashlib
import secrets


def generate_token() -> tuple[str, str]:
    """(raw_token, token_hash) qaytaradi. raw faqat mijozga linkda beriladi."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
