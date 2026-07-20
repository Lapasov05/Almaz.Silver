"""FastAPI ilova fabrikasi — modul routerlarini yig'adi (TZ 4-bo'lim).

Barcha modul routerlari + hardening (structured logging, request middleware, readiness).
"""
import time
import uuid

import structlog
from fastapi import FastAPI, Request
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine
from app.core.exceptions import register_exception_handlers
from app.core.logging_config import configure_logging, get_logger
from app.core.redis import get_redis
from app.modules.ai.router import router as ai_router
from app.modules.analytics.router import router as analytics_router
from app.modules.audit.router import router as audit_router
from app.modules.catalog.router import router as catalog_router
from app.modules.delivery.checkout import router as checkout_router
from app.modules.delivery.router import router as delivery_router
from app.modules.identity.admin_router import router as rbac_router
from app.modules.identity.router import router as identity_router
from app.modules.inbox.router import router as inbox_router
from app.modules.inbox.webhooks import router as webhooks_router
from app.modules.notifications.router import router as notifications_router
from app.modules.orders.router import router as orders_router
from app.modules.payments.router import router as payments_router
from app.modules.settings.router import router as settings_router

settings = get_settings()


def create_app() -> FastAPI:
    configure_logging()
    log = get_logger("almaz.request")

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        docs_url="/docs",
    )

    register_exception_handlers(app)

    # TZ 16: har so'rov uchun request_id + strukturaviy log (metod/yo'l/status/vaqt)
    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(request_id=request_id, path=request.url.path)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        response.headers["X-Request-ID"] = request_id
        log.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response

    @app.get("/health", tags=["system"])
    async def health() -> dict:
        """Liveness probe — servis ko'tarilganini tekshirish uchun."""
        return {"status": "ok", "app": settings.app_name, "environment": settings.environment}

    @app.get("/health/ready", tags=["system"])
    async def readiness() -> dict:
        """Readiness probe — DB va Redis ulanishini tekshiradi (TZ 16)."""
        checks: dict[str, str] = {}
        ok = True
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception:  # noqa: BLE001
            checks["database"] = "fail"
            ok = False
        try:
            await (await get_redis()).ping()
            checks["redis"] = "ok"
        except Exception:  # noqa: BLE001
            checks["redis"] = "fail"
            ok = False
        if not ok:
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=503, content={"status": "unavailable", "checks": checks})
        return {"status": "ready", "checks": checks}

    # Modul routerlari (TZ 4-bo'lim)
    app.include_router(identity_router)
    app.include_router(settings_router)
    app.include_router(catalog_router)
    app.include_router(inbox_router)
    app.include_router(webhooks_router)
    app.include_router(ai_router)
    app.include_router(orders_router)
    app.include_router(delivery_router)
    app.include_router(checkout_router)
    app.include_router(payments_router)
    app.include_router(rbac_router)
    app.include_router(analytics_router)
    app.include_router(audit_router)
    app.include_router(notifications_router)

    return app


app = create_app()
