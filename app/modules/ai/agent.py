import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.modules.ai.coalesce import mark_answered
from app.modules.ai.memory import build_conversation_input
from app.modules.ai.llm.base import LLMProvider
from app.modules.ai.prompt_registry import get_ai_text
from app.modules.ai.prompts import build_system_prompt
from app.modules.ai.tools import TOOL_SPECS, ToolContext, dispatch
from app.modules.inbox.repository import InboxRepository
from app.modules.inbox.service import InboxService
from app.modules.settings.repository import SettingsRepository

settings = get_settings()
logger = logging.getLogger(__name__)


@dataclass
class AgentOutcome:
    status: str
    reason: str | None = None
    reply: str | None = None
    message_id: uuid.UUID | None = None
    used_tools: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    state: str | None = None


class Agent:
    def __init__(self, db, provider: LLMProvider | None):
        self.db = db
        self.provider = provider

    async def respond(
        self,
        conversation_id: uuid.UUID,
        *,
        force: bool = False,
        started_at: float | None = None,
    ) -> AgentOutcome:
        """`started_at` — task boshlangan payt; insonsimon pauza shundan hisoblanadi."""
        inbox_repo = InboxRepository(self.db)
        conversation = await inbox_repo.get_conversation(conversation_id)
        if conversation is None:
            raise NotFoundError("Suhbat topilmadi")
        if not bool(await self._setting("ai_enabled", True)):
            return AgentOutcome(status="skipped", reason="ai_disabled", state=conversation.ai_state)
        if conversation.status == "closed":
            return AgentOutcome(status="skipped", reason="closed", state=conversation.ai_state)
        if force:
            conversation.ai_enabled = True
            conversation.ai_paused_until = None
        else:
            if not conversation.ai_enabled:
                return AgentOutcome(
                    status="skipped",
                    reason="ai_disabled_conversation",
                    state=conversation.ai_state,
                )
            if conversation.ai_paused_until and conversation.ai_paused_until > datetime.now(timezone.utc):
                return AgentOutcome(status="skipped", reason="operator_handoff", state=conversation.ai_state)
        if self.provider is None:
            return AgentOutcome(status="skipped", reason="no_provider", state=conversation.ai_state)

        inbox_service = InboxService(inbox_repo)
        await inbox_service.send_typing(conversation)
        if started_at is None:
            started_at = time.monotonic()
        # Javob shu xabargacha bo'lgan hammasini qamrab oladi — qolgan tasklar takrorlamasin
        answered_upto = getattr(await inbox_repo.get_last_incoming_message(conversation_id), "created_at", None)
        prompt_version = int(await self._setting("prompt_version", 3) or 3)
        base_prompt = await get_ai_text(self.db, "ai_system_prompt_v3")
        override = await self._setting("system_prompt_override", None)
        current_date = datetime.now(ZoneInfo("Asia/Tashkent")).date().isoformat()
        instructions = build_system_prompt(
            prompt_version,
            base_prompt,
            override,
            platform=conversation.channel,
            current_date=current_date,
        )
        input_items = await build_conversation_input(
            self.db,
            conversation,
            settings.ai_memory_message_count,
        )
        model = str(await self._setting("llm_model", settings.ai_default_model) or settings.ai_default_model)
        context = ToolContext(db=self.db, conversation=conversation)
        used_tools: list[str] = []
        tool_trace: list[dict] = []
        reply = ""

        try:
            for _ in range(settings.ai_max_tool_iterations):
                response = await self.provider.complete(
                    instructions,
                    input_items,
                    TOOL_SPECS,
                    model=model,
                )
                input_items.extend(response.output_items)
                if not response.function_calls:
                    reply = response.content
                    break
                for call in response.function_calls:
                    used_tools.append(call.name)
                    try:
                        output = await dispatch(call.name, call.arguments, context)
                    except Exception as exc:
                        logger.exception("AI function call bajarilmadi: %s", call.name)
                        await self.db.rollback()
                        output = {"ok": False, "error": str(exc)}
                    safe_output = json.loads(json.dumps(output, ensure_ascii=False, default=str))
                    tool_trace.append({
                        "name": call.name,
                        "arguments": call.arguments,
                        "output": safe_output,
                    })
                    input_items.append({
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(safe_output, ensure_ascii=False),
                    })
            if not reply:
                reply = await get_ai_text(self.db, "ai_msg_fallback")
                conversation.ai_paused_until = datetime.now(timezone.utc) + timedelta(
                    minutes=int(await self._setting("handoff_pause_minutes", 60) or 60)
                )
        except Exception as exc:
            logger.exception("AI javob berolmadi (conversation=%s)", conversation.id)
            return AgentOutcome(
                status="skipped",
                reason=f"llm_error: {type(exc).__name__}: {str(exc)[:300]}",
                used_tools=used_tools,
                state=conversation.ai_state,
            )

        remaining = settings.ai_reply_delay_seconds - (time.monotonic() - started_at)
        if remaining > 0:
            await inbox_service.send_typing(conversation)
            await asyncio.sleep(remaining)
        message = await inbox_service.ai_send(conversation, reply)
        if tool_trace:
            message.tool_call = {"calls": tool_trace}
        await self.db.commit()
        await mark_answered(conversation_id, answered_upto)
        return AgentOutcome(
            status="replied",
            reply=reply,
            message_id=message.id,
            used_tools=used_tools,
            state=conversation.ai_state,
        )

    async def _setting(self, key: str, default: Any) -> Any:
        setting = await SettingsRepository(self.db).get(key)
        return setting.value if setting is not None else default
