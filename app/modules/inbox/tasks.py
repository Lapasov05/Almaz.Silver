"""inbox Celery task'lari — og'ir/asinxron ishlar (TZ 4/5).

Kelgan xabar sinxron saqlanadi (webhook), keyin bu task AI agentni ishga tushiradi.
"""
import asyncio
import logging
import uuid

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _run_agent(message_id: str) -> str:
    # Har task o'z sessiyasi/loop'ida (task_session — NullPool)
    from app.core.database import task_session
    from app.modules.ai.service import AgentService

    async with task_session() as db:
        outcome = await AgentService(db).handle_incoming_message(uuid.UUID(message_id))
        logger.info("inbox.process_incoming: %s (status=%s tools=%s)", message_id, outcome.status, outcome.used_tools)
        return outcome.status


@celery_app.task(name="inbox.process_incoming")
def process_incoming(message_id: str) -> str:
    """Kelgan xabarni AI agent orqali qayta ishlash (TZ 7)."""
    return asyncio.run(_run_agent(message_id))


async def _run_reengagement() -> int:
    from app.core.database import task_session
    from app.modules.inbox.reengagement import ReengagementService

    async with task_session() as db:
        sent = await ReengagementService(db).run()
        if sent:
            logger.info("inbox.proactive_reengage: %s ta suhbat qayta jalb qilindi", sent)
        return sent


@celery_app.task(name="inbox.proactive_reengage")
def proactive_reengage() -> int:
    """Proaktiv qayta jalb (TZ 17) — Celery beat davriy ishga tushiradi."""
    return asyncio.run(_run_reengagement())


def enqueue_incoming(message_id) -> None:
    """Webhook'dan best-effort navbatga qo'yish — broker yo'q bo'lsa ham 200 OK buzilmaydi."""
    try:
        process_incoming.delay(str(message_id))
    except Exception:  # noqa: BLE001 — navbat ishlamasa ham xabar saqlangan
        logger.warning("process_incoming enqueue muvaffaqiyatsiz (message_id=%s)", message_id, exc_info=True)
