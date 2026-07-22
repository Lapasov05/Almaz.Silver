"""Ilova xatolari va ularning HTTP handlerlari.

Service qatlami domen xatolarini ko'taradi; API qatlami ularni JSON javobga aylantiradi.
"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
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
    """Domen xatolarini yagona formatdagi JSON javobga o'girish.

    Frontend uchun kontrakt: `detail` DOIM matn (string). Validatsiya xatosida
    qo'shimcha `errors` ro'yxati beriladi (maydon → xabar).
    """

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        """422 — FastAPI standart formati o'rniga frontend uchun barqaror shakl."""
        errors = [
            {
                # loc: ("body", "field", ...) -> "field"
                "field": ".".join(str(p) for p in err.get("loc", []) if p not in ("body", "query", "path")),
                "message": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={"detail": "Yuborilgan ma'lumot noto'g'ri", "errors": errors},
        )
