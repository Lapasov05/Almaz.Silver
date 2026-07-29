"""Fayl saqlash yordamchisi — baytlarni `uploads/` ga yozadi va public URL qaytaradi.

`/files` router (operator yuklashi) va AI chek oqimi (mijoz yuborgan rasmni saqlash) shu
yagona funksiyani ishlatadi. URL — `{public_base_url}/uploads/...` (nginx orqali ochiladi),
shuning uchun mijoz/owner/operator hammasi ko'ra oladi.
"""
import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings

settings = get_settings()

# Ruxsat etilgan kengaytmalar (rasm + hujjat)
ALLOWED_EXTS = {"jpg", "jpeg", "png", "webp", "gif", "pdf", "heic"}


def _dest_dir() -> Path:
    # uploads/YYYY/MM/ — papka juda katta bo'lib ketmasligi uchun
    now = datetime.now(timezone.utc)
    d = Path(settings.upload_dir) / f"{now:%Y}" / f"{now:%m}"
    d.mkdir(parents=True, exist_ok=True)
    return d


async def save_bytes(data: bytes, ext: str) -> str:
    """Baytlarni saqlaydi va tashqi (public) URL qaytaradi.

    `ext` — kengaytma (nuqtasiz), oq ro'yxatda bo'lishi shart. UUID nom (path traversal yo'q).
    """
    ext = (ext or "").lstrip(".").lower() or "jpg"
    if ext not in ALLOWED_EXTS:
        ext = "jpg"
    name = f"{uuid.uuid4().hex}.{ext}"
    dest = _dest_dir() / name
    await asyncio.to_thread(dest.write_bytes, data)
    rel = dest.relative_to(settings.upload_dir).as_posix()
    return f"{settings.public_base_url.rstrip('/')}/uploads/{rel}"
