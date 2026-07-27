"""AI javob oqimi diagnostikasi — nega javob bermayapti (aniq sababни ko'rsatadi).

Ishga tushirish:
    make test-ai                 # oxirgi instagram suhbatига AI javob berib ko'radi
    make test-ai CH=telegram     # telegram

Nima qiladi (production yo'li bilan):
  1) LLM provider aniqlanadimi (openai/api_key DB'да)?
  2) Gating: ai_enabled(global), conv.ai_enabled, status, ai_paused_until.
  3) AgentService.respond() ishga tushiriladi — outcome yoki TO'LIQ exception.
  4) Javob xabari delivery_status (send yiqilса ko'rinadi).

Eslatma: bu HAQIQIY javob yuboradi (oxirgi real mijozga). O'zingizga/test akkauntга ishlating.
"""
import asyncio
import os
import traceback

from sqlalchemy import select

from app.core.database import SessionLocal
from app.modules.ai.llm.factory import get_llm_provider
from app.modules.ai.service import AgentService
from app.modules.inbox.models import Conversation, Customer, Message
from app.modules.settings.repository import SettingsRepository


async def latest_conv(db, channel: str):
    return (await db.execute(
        select(Conversation)
        .join(Customer, Conversation.customer_id == Customer.id)
        .where(Customer.channel == channel, Customer.external_id.notlike("selftest-%"),
               Customer.deleted_at.is_(None))
        .order_by(Conversation.last_activity_at.desc())
        .limit(1)
    )).scalar_one_or_none()


async def main() -> None:
    channel = (os.environ.get("CH") or "instagram").strip()
    print("═" * 62)
    print(f"  AI javob diagnostikasi — kanal: {channel}")
    print("═" * 62)

    async with SessionLocal() as db:
        # 1) Provider
        prov = await get_llm_provider(db)
        print(f"\n[1] LLM provider: {type(prov).__name__ if prov else 'None'}")
        if prov is None:
            print("    ❌ Provider yo'q -> AI jim. openai/api_key DB'да bormi? llm_provider=openai?")

        # 2) Global setting
        s = await SettingsRepository(db).get("ai_enabled")
        ai_glob = s.value if s else "(yo'q -> default True)"
        print(f"[2] ai_enabled (global): {ai_glob}")

        # 3) Target conversation
        conv = await latest_conv(db, channel)
        if not conv:
            print(f"\n⚠️  {channel} bo'yicha real suhbat yo'q — avval DM yozing.")
            return
        print(f"\n[3] Suhbat: {conv.id}")
        print(f"    ai_enabled={conv.ai_enabled}  status={conv.status}  "
              f"ai_state={conv.ai_state}  ai_paused_until={conv.ai_paused_until}")

        # 4) Agentni ishga tushirish
        print("\n[4] AgentService.respond() ...")
        try:
            outcome = await AgentService(db).respond(conv.id)
            print(f"    status = {outcome.status}")
            print(f"    reason = {outcome.reason}")
            print(f"    reply  = {outcome.reply!r}")
            print(f"    tools  = {outcome.used_tools}")
            print(f"    state  = {outcome.state}")
            if outcome.message_id:
                m = await db.get(Message, outcome.message_id)
                ds = m.delivery_status if m else "?"
                print(f"    javob delivery_status = {ds}"
                      + ("   ❌ (send yiqildi — logда outbound_send_failed)" if ds == "failed" else "   ✅"))
            if outcome.status == "skipped":
                print(f"\n    ⚠️  AI javob bermadi, sabab: {outcome.reason}")
                _explain(outcome.reason)
        except Exception:
            print("    ❌ EXCEPTION (asl sabab — pastда to'liq):\n")
            traceback.print_exc()
            print("\n    (Ko'pincha: OpenAI kaliti/model/kvota yoki tarmoq xatosi.)")

    print("\n" + "═" * 62)


def _explain(reason: str | None) -> None:
    tips = {
        "ai_disabled": "Settings ai_enabled=false -> yoqing (PUT /settings/ai_enabled true).",
        "ai_disabled_conversation": "Shu suhbatда AI o'chirilgan (conv.ai_enabled=false) -> inbox'дан yoqing.",
        "closed": "Suhbat yopiq (status=closed).",
        "operator_handoff": "ai_paused_until kelajakда -> operator yozgan, pauza tugashini kuting.",
        "no_provider": "OpenAI kaliti yo'q -> DB'га openai/api_key qo'ying.",
    }
    if reason in tips:
        print(f"       -> {tips[reason]}")


if __name__ == "__main__":
    asyncio.run(main())
