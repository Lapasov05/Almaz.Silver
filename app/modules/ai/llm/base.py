"""LLM provider umumiy tiplari va interfeysi (provayderdan mustaqil)."""
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class LlmToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LlmMessage:
    """Bitta suhbat xabari (provayderga uzatiladigan yagona format)."""

    role: str  # system | user | assistant | tool
    content: str | None = None
    tool_calls: list[LlmToolCall] = field(default_factory=list)  # assistant uchun
    tool_call_id: str | None = None  # tool natijasi uchun
    name: str | None = None  # tool nomi (tool roli uchun)


@dataclass
class LlmResult:
    content: str | None = None
    tool_calls: list[LlmToolCall] = field(default_factory=list)


class LLMProvider(Protocol):
    """Function-calling qo'llab-quvvatlaydigan LLM provayder interfeysi."""

    async def complete(
        self,
        messages: list[LlmMessage],
        tools: list[dict],
        *,
        model: str,
        temperature: float,
    ) -> LlmResult: ...
