"""Deterministik soxta LLM provayderi — test/dev uchun (kalit talab qilmaydi).

Skript orqali oldindan belgilangan qadamlarni qaytaradi:
- ("tool", name, args) → tool-call chiqaradi;
- ("text", "...") → yakuniy matn qaytaradi.
Skript tugasa, oxirgi user xabari asosida yengil default javob beradi.
"""
from app.modules.ai.llm.base import LlmMessage, LlmResult, LlmToolCall


class FakeProvider:
    def __init__(self, script: list[tuple] | None = None) -> None:
        self._script = list(script or [])
        self._i = 0
        self._counter = 0

    async def complete(
        self,
        messages: list[LlmMessage],
        tools: list[dict],
        *,
        model: str,
        temperature: float,
    ) -> LlmResult:
        if self._i < len(self._script):
            step = self._script[self._i]
            self._i += 1
            if step[0] == "tool":
                self._counter += 1
                return LlmResult(
                    tool_calls=[LlmToolCall(id=f"call_{self._counter}", name=step[1], arguments=step[2])]
                )
            return LlmResult(content=step[1])
        # Skript tugadi — oddiy javob
        return LlmResult(content="Assalomu alaykum! Sizga qanday yordam bera olaman?")
