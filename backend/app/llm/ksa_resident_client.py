from typing import AsyncIterator

from app.llm.base import LLMClient, LLMMessage, LLMResponse


class KSAResidentLLMClient(LLMClient):
    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        max_output_tokens: int = 1500,
        temperature: float = 0.2,
        response_format: str = "text",
        timeout_s: int = 30,
        request_id: str | None = None,
    ) -> LLMResponse:
        raise NotImplementedError("KSA-resident LLM adapter is deferred to pilot.")

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        max_output_tokens: int = 1500,
        temperature: float = 0.2,
        timeout_s: int = 60,
        request_id: str | None = None,
    ) -> AsyncIterator[str]:
        raise NotImplementedError("KSA-resident LLM adapter is deferred to pilot.")
