"""File upload API — fayl yuklaydi va ochib ko'rsa bo'ladigan to'liq URL qaytaradi.

Fayllar `settings.upload_dir` (Docker volume) ga saqlanadi va `/uploads/<nom>` orqali
(nginx → API static) ochiladi. Xavfsizlik: kirish autentifikatsiya bilan, kengaytma oq ro'yxati,
UUID nom (path traversal yo'q), hajm cheklovi.
"""
from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.exceptions import AppError
from app.modules.files.service import ALLOWED_EXTS, save_bytes
from app.modules.identity.models import User

settings = get_settings()
router = APIRouter(prefix="/files", tags=["files"])


class UploadOut(BaseModel):
    url: str
    filename: str
    content_type: str | None
    size: int


async def _save(file: UploadFile) -> UploadOut:
    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in ALLOWED_EXTS:
        raise AppError(f"Ruxsat etilmagan fayl turi: .{ext or '?'} (ruxsat: {', '.join(sorted(ALLOWED_EXTS))})")

    data = await file.read()
    max_bytes = settings.upload_max_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise AppError(f"Fayl juda katta (maks {settings.upload_max_mb} MB)")
    if not data:
        raise AppError("Bo'sh fayl")

    url = await save_bytes(data, ext)
    rel = url.rsplit("/uploads/", 1)[-1]
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
