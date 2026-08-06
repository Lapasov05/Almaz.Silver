from app.modules.ai.llm.base import LlmFunctionCall, LlmResponse


class FakeProvider:
    def __init__(self, script: list[tuple] | None = None) -> None:
        self._script = list(script or [])
        self._index = 0
        self._counter = 0

    async def complete(
        self,
        instructions: str,
        input_items: list[dict],
        tools: list[dict],
        *,
        model: str,
    ) -> LlmResponse:
        if self._index < len(self._script):
            step = self._script[self._index]
            self._index += 1
            if step[0] == "tool":
                self._counter += 1
                call_id = f"call_{self._counter}"
                return LlmResponse(
                    function_calls=[LlmFunctionCall(call_id, step[1], step[2])],
                    output_items=[{
                        "type": "function_call",
                        "call_id": call_id,
                        "name": step[1],
                        "arguments": step[2],
                    }],
                )
            return LlmResponse(content=step[1])
        return LlmResponse(content="Assalomu alaykum! Sizga qanday yordam bera olaman?")
