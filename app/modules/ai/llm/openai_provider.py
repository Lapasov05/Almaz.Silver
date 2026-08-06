import copy
import json
from typing import Any

from openai import AsyncOpenAI

from app.modules.ai.llm.base import LlmFunctionCall, LlmResponse


class OpenAIProvider:
    def __init__(self, api_key: str, base_url: str = "") -> None:
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**kwargs)

    async def complete(
        self,
        instructions: str,
        input_items: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        model: str,
    ) -> LlmResponse:
        response = await self._client.responses.create(
            model=model,
            instructions=instructions,
            input=input_items,
            tools=[self._strict_tool(tool) for tool in tools],
            parallel_tool_calls=False,
            store=False,
        )
        output_items = [item.model_dump(exclude_none=True) for item in response.output]
        function_calls: list[LlmFunctionCall] = []
        for item in response.output:
            if getattr(item, "type", "") != "function_call":
                continue
            try:
                arguments = json.loads(getattr(item, "arguments", "") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            function_calls.append(
                LlmFunctionCall(
                    call_id=getattr(item, "call_id", ""),
                    name=getattr(item, "name", ""),
                    arguments=arguments,
                )
            )
        return LlmResponse(
            content=(response.output_text or "").strip(),
            function_calls=function_calls,
            output_items=output_items,
        )

    def _strict_tool(self, tool: dict[str, Any]) -> dict[str, Any]:
        source = copy.deepcopy(tool.get("function", tool))
        parameters = source.get("parameters") or {"type": "object", "properties": {}}
        self._strict_schema(parameters)
        return {
            "type": "function",
            "name": source["name"],
            "description": source.get("description", ""),
            "parameters": parameters,
            "strict": True,
        }

    def _strict_schema(self, schema: dict[str, Any]) -> None:
        if schema.get("type") == "object":
            properties = schema.setdefault("properties", {})
            originally_required = set(schema.get("required") or [])
            for name, value in properties.items():
                if name not in originally_required:
                    value_type = value.get("type")
                    if isinstance(value_type, str):
                        value["type"] = [value_type, "null"]
                    enum = value.get("enum")
                    if isinstance(enum, list) and None not in enum:
                        enum.append(None)
            schema["required"] = list(properties)
            schema["additionalProperties"] = False
            for value in properties.values():
                self._strict_schema(value)
        items = schema.get("items")
        if isinstance(items, dict):
            self._strict_schema(items)
