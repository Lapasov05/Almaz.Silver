"""File upload API — fayl yuklaydi va ochib ko'rsa bo'ladigan to'liq URL qaytaradi.

Fayllar `settings.upload_dir` (Docker volume) ga saqlanadi va `/uploads/<nom>` orqali
(nginx → API static) ochiladi. Xavfsizlik: kirish autentifikatsiya bilan, kengaytma oq ro'yxati,
UUID nom (path traversal yo'q), hajm cheklovi.
"""
import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.exceptions import AppError
from app.modules.identity.models import User

settings = get_settings()
router = APIRouter(prefix="/files", tags=["files"])

# Ruxsat etilgan kengaytmalar (rasm + hujjat)
_ALLOWED = {"jpg", "jpeg", "png", "webp", "gif", "pdf", "heic"}


class UploadOut(BaseModel):
    url: str
    filename: str
    content_type: str | None
    size: int


def _dest_dir() -> Path:
    # uploads/YYYY/MM/ — papka juda katta bo'lib ketmasligi uchun
    now = datetime.now(timezone.utc)
    d = Path(settings.upload_dir) / f"{now:%Y}" / f"{now:%m}"
    d.mkdir(parents=True, exist_ok=True)
    return d


async def _save(file: UploadFile) -> UploadOut:
    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in _ALLOWED:
        raise AppError(f"Ruxsat etilmagan fayl turi: .{ext or '?'} (ruxsat: {', '.join(sorted(_ALLOWED))})")

    data = await file.read()
    max_bytes = settings.upload_max_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise AppError(f"Fayl juda katta (maks {settings.upload_max_mb} MB)")
    if not data:
        raise AppError("Bo'sh fayl")

    name = f"{uuid.uuid4().hex}.{ext}"
    dest = _dest_dir() / name
    await asyncio.to_thread(dest.write_bytes, data)

    rel = dest.relative_to(settings.upload_dir).as_posix()
    url = f"{settings.public_base_url.rstrip('/')}/uploads/{rel}"
    return UploadOut(url=url, filename=rel, content_type=file.content_type, size=len(data))


@router.post("", response_model=UploadOut)
async def upload_file(
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
) -> UploadOut:
    """Bitta fayl yuklaydi va URL qaytaradi."""
    return await _save(file)


@router.post("/batch", response_model=list[UploadOut])
async def upload_files(
    files: list[UploadFile] = File(...),
    _: User = Depends(get_current_user),
) -> list[UploadOut]:
    """Bir nechta fayl yuklaydi va URL'lar ro'yxatini qaytaradi."""
    return [await _save(f) for f in files]
