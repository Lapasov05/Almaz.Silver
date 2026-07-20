"""AI Agent yadrosi (TZ 7) — memory → prompt → LLM tool-calling sikli → guardrail → javob.

Runtime ketma-ketligi (TZ 5): worker kelgan xabar uchun shu agentni ishga tushiradi.
Gating: `ai_enabled`, `ai_paused_until` (operator handoff), yopilgan suhbat.
"""
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.modules.ai import memory as memory_mod
from app.modules.ai.guardrail import enforce
from app.modules.ai.llm.base import LlmMessage, LLMProvider
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


class Agent:
    def __init__(self, db, provider: LLMProvider | None):
        self.db = db
        self.provider = provider

    async def respond(self, conversation_id: uuid.UUID) -> AgentOutcome:
        inbox_repo = InboxRepository(self.db)
        conv = await inbox_repo.get_conversation(conversation_id)
        if conv is None:
            raise NotFoundError("Suhbat topilmadi")

        # --- Gating (TZ 5/14) ---
        if not bool(await _setting(self.db, "ai_enabled", True)):
            return AgentOutcome(status="skipped", reason="ai_disabled")
        if conv.status == "closed":
            return AgentOutcome(status="skipped", reason="closed")
        now = datetime.now(timezone.utc)
        if conv.ai_paused_until is not None and conv.ai_paused_until > now:
            return AgentOutcome(status="skipped", reason="operator_handoff")
        if self.provider is None:
            logger.info("LLM provayder yo'q — AI jim (conv=%s)", conv.id)
            return AgentOutcome(status="skipped", reason="no_provider")

        # --- Prompt + memory (TZ 7.2/7.3) ---
        prompt_version = int(await _setting(self.db, "prompt_version", 1) or 1)
        override = await _setting(self.db, "system_prompt_override", None)
        system_prompt = build_system_prompt(prompt_version, override)
        messages = await memory_mod.build_messages(
            self.db, conv, conv.customer, system_prompt, settings.ai_memory_message_count
        )

        model = str(await _setting(self.db, "llm_model", settings.ai_default_model) or settings.ai_default_model)
        temperature = float(
            await _setting(self.db, "ai_temperature", settings.ai_default_temperature)
            or settings.ai_default_temperature
        )

        # --- Tool-calling sikli (TZ 7.4) ---
        ctx = ToolContext(db=self.db, conversation=conv)
        used_tools: list[str] = []
        text: str | None = None
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
            # Sikl tugadi — operatorga o'tkazamiz
            text = "Kechirasiz, so'rovingizni to'liq bajara olmadim. Operator tez orada bog'lanadi."
            used_tools.append("handoff_to_operator")
            conv.ai_state = AiState.handed_off.value

        # --- Guardrail (TZ 15, KRITIK) ---
        guard = enforce(text)
        if guard.violations:
            logger.warning("Guardrail buzilishi tuzatildi: %s (conv=%s)", guard.violations, conv.id)

        # --- Javobni yuborish (AI, pauza qo'ymaydi) ---
        inbox_svc = InboxService(inbox_repo)
        message = await inbox_svc.ai_send(conv, guard.text)

        # --- State machine (TZ 7.1) ---
        next_state = infer_next_state(AiState(conv.ai_state), used_tools)
        conv.ai_state = next_state.value
        await self.db.commit()

        return AgentOutcome(
            status="replied",
            reply=guard.text,
            message_id=message.id,
            used_tools=used_tools,
            violations=guard.violations,
            state=conv.ai_state,
        )
