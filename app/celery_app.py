"""Celery ilovasi — RabbitMQ broker + Redis result backend (TZ 3-bo'lim).

Worker entrypoint: `celery -A app.celery_app:celery_app worker`.
Og'ir ishlar (LLM chaqiruvi, IG/TG javob, notification) keyingi fazalarda shu yerga qo'shiladi.
"""
from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "almaz",
    broker=settings.rabbitmq_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Tashkent",
    enable_utc=True,
    task_track_started=True,
    # Test/dev: broker'siz inline ishlash (TZ webhook 200 OK oqimini buzmaslik uchun)
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=False,
    # Broker qisqa timeout — webhook enqueue hech qachon uzoq bloklamasin
    broker_transport_options={"max_retries": 1},
    broker_connection_retry_on_startup=True,
)

# Task modullarini ro'yxatga olish (inbox inbound processing — Faza 3 AI ilmog'i)
celery_app.autodiscover_tasks(["app.modules.inbox"])

# TZ 17: proaktiv qayta jalb — Celery beat davriy vazifasi (`celery ... beat`)
celery_app.conf.beat_schedule = {
    "proactive-reengage": {
        "task": "inbox.proactive_reengage",
        "schedule": float(settings.reengagement_interval_minutes * 60),
    },
}


@celery_app.task(name="health.ping")
def ping() -> str:
    """Worker tirikligini tekshirish uchun oddiy task."""
    return "pong"
