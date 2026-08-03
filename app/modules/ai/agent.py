"""AI Agent yadrosi (TZ 7) — memory → prompt → LLM tool-calling sikli → guardrail → javob.

Runtime ketma-ketligi (TZ 5): worker kelgan xabar uchun shu agentni ishga tushiradi.
Gating: `ai_enabled`, `ai_paused_until` (operator handoff), yopilgan suhbat.
"""
import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.modules.ai import memory as memory_mod
from app.modules.ai.guardrail import enforce
from app.modules.ai.llm.base import LlmMessage, LLMProvider
from app.modules.ai.prompt_registry import get_ai_text
from app.modules.ai.prompts import build_system_prompt
from app.modules.ai.state_machine import infer_next_state
from app.modules.ai.tools import TOOL_SPECS, ToolContext, dispatch
from app.modules.inbox.models import AiState
from app.modules.inbox.repository import InboxRepository
from app.modules.inbox.service import InboxService
from app.modules.settings.repository import SettingsRepository

settings = get_settings()
logger = logging.getLogger(__name__)


@dataclass
class AgentOutcome:
    status: str  # replied | skipped
    reason: str | None = None
    reply: str | None = None
    message_id: uuid.UUID | None = None
    used_tools: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    state: str | None = None


async def _setting(db, key: str, default: Any) -> Any:
    setting = await SettingsRepository(db).get(key)
    return setting.value if setting is not None else default


async def _is_superseded(db, conv_id, trigger_message_id) -> bool:
    """Trigger xabaridan keyin YANGI kiruvchi (mijoz) xabar bo'lsa True — bu javob eskirgan.

    Debounce: mijoz tez ketma-ket bir nechta xabar yozsa, faqat OXIRGI xabar javob oladi
    (avvalgilari 'superseded' bo'lib jim o'tadi) — natijada bitta yaxlit javob chiqadi.
    """
    if trigger_message_id is None:
        return False
    from sqlalchemy import func, select

    from app.modules.inbox.models import Message

    trig = await db.get(Message, trigger_message_id)
    if trig is None:
        return False
    res = await db.execute(
        select(func.count()).select_from(Message).where(
            Message.conversation_id == conv_id,
            Message.direction == "incoming",
            Message.created_at > trig.created_at,
        )
    )
    return int(res.scalar_one()) > 0


async def _latest_incoming_has_image(db, conv_id) -> bool:
    """Oxirgi kiruvchi xabar rasm (attachment) bo'lsa True — to'lov cheki bo'lishi mumkin."""
    from sqlalchemy import select

    from app.modules.inbox.models import Message

    latest = (await db.execute(
        select(Message).where(Message.conversation_id == conv_id, Message.direction == "incoming")
        .order_by(Message.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if latest is None:
        return False
    for att in (latest.attachments or []):
        if isinstance(att, dict) and att.get("type") == "image" and att.get("url"):
            return True
    return False


async def _active_order_context(db, conv) -> str | None:
    """Mijozning FAOL buyurtmasi bo'lsa — holat + mahsulot + keyingi qadam kontekstini AI'ga beradi.

    Xotira/follow-up muammosini hal qiladi: AI har javobda joriy buyurtmani (mahsulot, o'lcham,
    gravirovka, jami, holat) biladi va to'g'ri keyingi qadamni bajaradi (karta / chek / sabr).
    """
    from app.modules.catalog.repository import CatalogRepository
    from app.modules.orders.repository import OrdersRepository

    order = await OrdersRepository(db).get_current_order(conv.customer_id)
    if order is None:
        return None
    catalog = CatalogRepository(db)
    parts: list[str] = []
    for it in order.items:
        variant = await catalog.get_variant(it.variant_id)
        pname = "?"
        if variant is not None:
            prod = await catalog.get_product(variant.product_id)
            pname = prod.name_uz if prod is not None else "?"
        seg = pname
        if it.ring_size:
            seg += f", o'lcham {it.ring_size}"
        if it.engraving_text:
            eng = f", gravirovka '{it.engraving_text}'"
            if it.engraving_price:
                eng += f" (+{int(it.engraving_price)} so'm)"
            seg += eng
        parts.append(seg)
    products = "; ".join(parts) or "?"
    items_total = int(order.items_total or 0)
    fee = int(order.delivery_fee or 0)
    total = int(order.grand_total or 0)
    guide_key = f"ai_ctx_order_guide_{order.status}"
    guide = await get_ai_text(db, guide_key)
    if not guide:
        guide = await get_ai_text(db, "ai_ctx_order_guide_default")
    hint = ""
    if order.status in ("waiting_payment", "payment_review") and await _latest_incoming_has_image(db, conv.id):
        hint = await get_ai_text(db, "ai_ctx_order_receipt_hint")
    # Shikoyat raqami — mijoz buyurtma bo'yicha norozilik bildirsa AI shu raqamni beradi
    complaint = await _setting(db, "complaint_phone", "")
    if complaint:
        hint += f" [Shikoyat/norozilik bo'lsa mijozga bu raqamni ber: {complaint}]"
    return await get_ai_text(
        db, "ai_ctx_order",
        order_no=order.order_no, products=products, items_total=items_total,
        fee=fee, grand_total=total, status=order.status, guide=guide, hint=hint,
    )


async def _instagram_context(db, conv) -> str | None:
    """Oxirgi kiruvchi xabar IG link/story-javob bo'lsa — mahsulotni topib AI'ga kontekst beradi."""
    from sqlalchemy import select

    from app.modules.catalog.repository import CatalogRepository
    from app.modules.catalog.search import extract_instagram_ref, is_instagram_url
    from app.modules.catalog.service import CatalogService
    from app.modules.inbox.models import Message

    latest = (await db.execute(
        select(Message)
        .where(Message.conversation_id == conv.id, Message.direction == "incoming")
        .order_by(Message.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    if latest is None:
        return None
    ref = None
    is_story_reply = False
    for att in (latest.attachments or []):
        if not isinstance(att, dict):
            continue
        # Bizning story'ga javob (reply_to.story) — media_id
        if att.get("type") == "ig_story" and att.get("story_ref"):
            ref = att["story_ref"]
            is_story_reply = True
            break
        # Mijoz postni/reelni ULASHsa: attachment url = IG permalink (share/ig_reel/story_mention).
        # Faqat haqiqiy /p/·/reel/·/stories/ havolasini olamiz (rasm CDN url'ini emas).
        url = att.get("url")
        if url and extract_instagram_ref(url) is not None:
            ref = url
            break
    if ref is None and latest.content and is_instagram_url(latest.content):
        ref = latest.content
    if ref is None:
        return None
    catalog_repo = CatalogRepository(db)
    product = await CatalogService(catalog_repo).resolve_instagram_media(ref)
    if product is None and is_story_reply:
        # Story-javob: webhook story ID permalink ID'dan farq qiladi -> exact match ishlamaydi.
        # Aktiv (muddati o'tmagan) story faqat BITTA mahsulotда bo'lsa -> o'shanga bog'laymiz.
        story_products = await catalog_repo.list_active_story_products()
        if len(story_products) == 1:
            product = story_products[0]
    if product is None:
        return await get_ai_text(db, "ai_ctx_instagram_not_found")
    avail = product.available
    tip = await get_ai_text(db, "ai_ctx_instagram_tip_instock" if avail > 0 else "ai_ctx_instagram_tip_outstock")
    return await get_ai_text(
        db, "ai_ctx_instagram_found",
        name=product.name_uz, price=product.effective_price, avail=avail, tip=tip,
    )


async def _business_context(db, conv) -> str | None:
    """Do'kon FAKTLARI (har javobga) — offline do'kon, kelib olish, operator raqami.

    AI'ning "faqat onlayn ishlaymiz" kabi NOTO'G'RI gaplarini oldini oladi (do'kon jismoniy).
    Qiymatlar settingsdan — operator o'zgartira oladi.
    """
    parts: list[str] = []
    if bool(await _setting(db, "store_offline", True)):
        addr = (await _setting(db, "store_address", "") or "").strip()
        hours = (await _setting(db, "store_work_hours", "") or "").strip()
        line = ("Do'kon JISMONIY (offline) — mijoz do'konga kelib mahsulotni O'ZI ham olishi mumkin"
                if bool(await _setting(db, "store_pickup_enabled", True))
                else "Do'kon jismoniy (offline)")
        if addr:
            line += f". Do'kon manzili: {addr}"
        if hours:
            line += f" (ish vaqti: {hours})"
        line += (". Kela olmasa — yetkazib beramiz. HECH QACHON 'faqat onlayn buyurtma qabul qilamiz' "
                 "yoki 'do'konga kelib bo'lmaydi' DEMA — bu NOTO'G'RI.")
        parts.append(line)
    op = (await _setting(db, "operator_phone", "") or "").strip()
    if op:
        parts.append(f"Mijoz telefon raqam / operator / jonli aloqa so'rasa shu raqamni ber: {op}")
    if not parts:
        return None
    return "[Do'kon faktlari — shularga amal qil: " + " ".join(parts) + "]"


async def _first_ai_message(db, conv_id) -> bool:
    """Bu suhbatда hali AI xabar YUBORMAGAN bo'lsa True (test-rejim bildirishnomasi bir marta uchun)."""
    from sqlalchemy import func, select

    from app.modules.inbox.models import Message

    res = await db.execute(
        select(func.count()).select_from(Message).where(
            Message.conversation_id == conv_id, Message.sender_type == "ai"
        )
    )
    return int(res.scalar_one()) == 0


class Agent:
    def __init__(self, db, provider: LLMProvider | None):
        self.db = db
        self.provider = provider

    async def respond(
        self, conversation_id: uuid.UUID, *, force: bool = False, trigger_message_id: uuid.UUID | None = None
    ) -> AgentOutcome:
        """AI javobini ishga tushiradi.

        force=True (operator override): suhbat darajasidagi bloklarни (pauza/handoff/o'chirilган)
        yorib o'tadi — AI'ni QAYTA ISHGA SOLADI (ai_paused_until tozalanadi, ai_enabled=True) va
        darhol javob beradi. Global kill-switch (`ai_enabled` setting) va yopiq suhbat baribir hurmat.
        """
        inbox_repo = InboxRepository(self.db)
        conv = await inbox_repo.get_conversation(conversation_id)
        if conv is None:
            raise NotFoundError("Suhbat topilmadi")

        # --- Gating (TZ 5/14) ---
        if not bool(await _setting(self.db, "ai_enabled", True)):
            return AgentOutcome(status="skipped", reason="ai_disabled")  # global kill-switch (force ham hurmat)
        if conv.status == "closed":
            return AgentOutcome(status="skipped", reason="closed")
        if force:
            # Operator qo'lда AI'ни qaytaradi: pauza/handoffни ol, suhbatда AI'ni yoq
            conv.ai_paused_until = None
            conv.ai_enabled = True
        else:
            if not conv.ai_enabled:
                return AgentOutcome(status="skipped", reason="ai_disabled_conversation")  # suhbatда o'chirilgan
            now = datetime.now(timezone.utc)
            if conv.ai_paused_until is not None and conv.ai_paused_until > now:
                return AgentOutcome(status="skipped", reason="operator_handoff")  # vaqtincha pauza
        if self.provider is None:
            # LLM hali ulanmagan (tool'lar keyin qo'shiladi) — birinchi xabarga BOSHLANG'ICH salom
            greeting = await get_ai_text(self.db, "ai_greeting_text")
            if greeting and AiState(conv.ai_state) == AiState.greeting:
                message = await InboxService(inbox_repo).ai_send(conv, greeting)
                conv.ai_state = AiState.browsing.value
                await self.db.commit()
                return AgentOutcome(status="replied", reply=greeting, message_id=message.id, state=conv.ai_state)
            logger.info("LLM provayder yo'q — AI jim (conv=%s)", conv.id)
            return AgentOutcome(status="skipped", reason="no_provider")

        # Debounce (LLM'dan OLDIN): bu task ishga tushguncha mijoz yana yozgan bo'lsa — jim o'tamiz,
        # oxirgi xabar taskи to'liq kontekst bilan javob beradi (OpenAI chaqiruvini ham tejaydi).
        if not force and await _is_superseded(self.db, conv.id, trigger_message_id):
            return AgentOutcome(status="skipped", reason="superseded", state=conv.ai_state)

        # Javob tayyorlanmoqda — "yozyapti..." indikatorini yuboramiz + pauza uchun vaqt boshi
        inbox_svc = InboxService(inbox_repo)
        await inbox_svc.send_typing(conv)
        reply_started = time.monotonic()

        # --- Prompt + memory (TZ 7.2/7.3) ---
        prompt_version = int(await _setting(self.db, "prompt_version", 1) or 1)
        base_prompt = await get_ai_text(self.db, "ai_system_prompt")  # DB (registr) — asosiy prompt
        override = await _setting(self.db, "system_prompt_override", None)  # eski override (ustun)
        system_prompt = build_system_prompt(prompt_version, base_prompt, override)
        # --- Tool-calling sikli (TZ 7.4) ---
        ctx = ToolContext(db=self.db, conversation=conv)
        used_tools: list[str] = []
        text: str | None = None
        try:
            messages = await memory_mod.build_messages(
                self.db, conv, conv.customer, system_prompt, settings.ai_memory_message_count
            )
            # Instagram post/story konteksti (mijoz link/story-javob yuborgan bo'lsa) — grounding
            ig_ctx = await _instagram_context(self.db, conv)
            if ig_ctx:
                messages.insert(1, LlmMessage(role="system", content=ig_ctx))
            # Faol buyurtma konteksti (xotira/follow-up: holat, mahsulot, keyingi qadam)
            order_ctx = await _active_order_context(self.db, conv)
            if order_ctx:
                messages.insert(1, LlmMessage(role="system", content=order_ctx))
            # Do'kon faktlari (offline do'kon, kelib olish, operator raqami) — har javobга grounding
            biz_ctx = await _business_context(self.db, conv)
            if biz_ctx:
                messages.insert(1, LlmMessage(role="system", content=biz_ctx))
            model = str(
                await _setting(self.db, "llm_model", settings.ai_default_model) or settings.ai_default_model
            )
            temperature = float(
                await _setting(self.db, "ai_temperature", settings.ai_default_temperature)
                or settings.ai_default_temperature
            )
            for _ in range(settings.ai_max_tool_iterations):
                result = await self.provider.complete(
                    messages, TOOL_SPECS, model=model, temperature=temperature
                )
                if result.tool_calls:
                    messages.append(
                        LlmMessage(role="assistant", content=result.content, tool_calls=result.tool_calls)
                    )
                    for tc in result.tool_calls:
                        used_tools.append(tc.name)
                        try:
                            output = await dispatch(tc.name, tc.arguments, ctx)
                        except Exception as exc:  # noqa: BLE001 — tool xatosi suhbatni to'xtatmasin
                            logger.warning("Tool '%s' xato: %s", tc.name, exc)
                            output = {"error": str(exc)}
                        messages.append(
                            LlmMessage(
                                role="tool",
                                tool_call_id=tc.id,
                                name=tc.name,
                                content=json.dumps(output, ensure_ascii=False, default=str),
                            )
                        )
                    continue
                text = result.content or ""
                break
            else:
                # Sikl tugadi — operatorga o'tkazamiz (AI VAQTINCHALIK pauza, doimiy o'chirilmaydi)
                text = await get_ai_text(self.db, "ai_msg_fallback")
                used_tools.append("handoff_to_operator")
                conv.ai_state = AiState.handed_off.value
                minutes = int(await _setting(self.db, "handoff_pause_minutes", 60) or 60)
                conv.ai_paused_until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        except Exception as exc:  # noqa: BLE001
            # LLM/OpenAI xatosi 500 bermasin — jim skip + logда to'liq traceback + reason'да sabab
            logger.exception("AI javob berolmadi — LLM xatosi (conv=%s)", conv.id)
            return AgentOutcome(
                status="skipped",
                reason=f"llm_error: {type(exc).__name__}: {str(exc)[:300]}",
                state=conv.ai_state,
                used_tools=used_tools,
            )

        # --- Guardrail (TZ 15, KRITIK) ---
        guard = enforce(text)
        if guard.violations:
            logger.warning("Guardrail buzilishi tuzatildi: %s (conv=%s)", guard.violations, conv.id)

        # --- Insonsimon pauza: typing ko'rinib tursin, javob ~N soniyaда chiqsin ---
        remaining = settings.ai_reply_delay_seconds - (time.monotonic() - reply_started)
        if remaining > 0:
            await inbox_svc.send_typing(conv)   # LLM tez tugagan bo'lsa indikatorni yangilaymiz
            await asyncio.sleep(remaining)

        # Debounce (yuborishдан OLDIN): pauza/ishlov davomida mijoz yana yozgan bo'lsa — bu javobni
        # YUBORMAYMIZ (eskirdi). Oxirgi xabar taskи hammasiga bitta yaxlit javob beradi (bir xil javob spamи yo'q).
        # commit QILMAYMIZ — matnli javob ketmaydi; tool nojo'ya (order/ism) allaqachon o'z commitiga ega, saqlanadi.
        if not force and await _is_superseded(self.db, conv.id, trigger_message_id):
            return AgentOutcome(status="skipped", reason="superseded", state=conv.ai_state)

        # --- TEST rejimi: har suhbat boshida mijozga BIR MARTA test ekanini bildiramiz ---
        final_text = guard.text
        if bool(await _setting(self.db, "ai_test_mode", False)) and await _first_ai_message(self.db, conv.id):
            notice = await get_ai_text(self.db, "ai_msg_test_mode_notice")
            if notice:
                final_text = f"{notice}\n\n{final_text}"

        # --- Javobni yuborish (AI, pauza qo'ymaydi) ---
        message = await inbox_svc.ai_send(conv, final_text)

        # --- State machine (TZ 7.1) ---
        next_state = infer_next_state(AiState(conv.ai_state), used_tools)
        conv.ai_state = next_state.value
        await self.db.commit()

        return AgentOutcome(
            status="replied",
            reply=final_text,
            message_id=message.id,
            used_tools=used_tools,
            violations=guard.violations,
            state=conv.ai_state,
        )
