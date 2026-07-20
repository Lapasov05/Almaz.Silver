"""Ilova xatolari va ularning HTTP handlerlari.

Service qatlami domen xatolarini ko'taradi; API qatlami ularni JSON javobga aylantiradi.
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Barcha domen xatolari uchun baza."""

    status_code: int = 400

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class AuthError(AppError):
    """Autentifikatsiya muvaffaqiyatsiz (401)."""

    status_code = 401


class PermissionDenied(AppError):
    """Ruxsat yetarli emas (403) — TZ 13-bo'lim RBAC."""

    status_code = 403


class NotFoundError(AppError):
    """Resurs topilmadi (404)."""

    status_code = 404


def register_exception_handlers(app: FastAPI) -> None:
    """Domen xatolarini yagona formatdagi JSON javobga o'girish."""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})
