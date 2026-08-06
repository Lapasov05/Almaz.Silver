from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class LlmFunctionCall:
    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LlmResponse:
    content: str = ""
    function_calls: list[LlmFunctionCall] = field(default_factory=list)
    output_items: list[dict[str, Any]] = field(default_factory=list)


class LLMProvider(Protocol):
    async def complete(
        self,
        instructions: str,
        input_items: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        model: str,
    ) -> LlmResponse: ...
