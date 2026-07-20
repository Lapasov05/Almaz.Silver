"""OpenAI function-calling provayderi (TZ 3/7). Kalit bo'lganda ishlatiladi."""
import json

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.modules.ai.llm.base import LlmMessage, LlmResult, LlmToolCall

settings = get_settings()


def _to_openai_messages(messages: list[LlmMessage]) -> list[dict]:
    out: list[dict] = []
    for m in messages:
        if m.role == "assistant" and m.tool_calls:
            out.append(
                {
                    "role": "assistant",
                    "content": m.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                        }
                        for tc in m.tool_calls
                    ],
                }
            )
        elif m.role == "tool":
            out.append({"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content or ""})
        else:
            out.append({"role": m.role, "content": m.content or ""})
    return out


class OpenAIProvider:
    def __init__(self) -> None:
        kwargs: dict = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        self._client = AsyncOpenAI(**kwargs)

    async def complete(
        self,
        messages: list[LlmMessage],
        tools: list[dict],
        *,
        model: str,
        temperature: float,
    ) -> LlmResult:
        resp = await self._client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=_to_openai_messages(messages),
            tools=tools or None,
        )
        choice = resp.choices[0].message
        tool_calls = [
            LlmToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=json.loads(tc.function.arguments or "{}"),
            )
            for tc in (choice.tool_calls or [])
        ]
        return LlmResult(content=choice.content, tool_calls=tool_calls)
