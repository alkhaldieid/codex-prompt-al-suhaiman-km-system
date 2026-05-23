import time
from typing import AsyncIterator, Literal

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.llm.base import LLMClient, LLMMessage, LLMResponse


class OpenAIChatGPTClient(LLMClient):
    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.llm_model
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.llm_timeout_ms / 1000)

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        max_output_tokens: int = 1500,
        temperature: float = 0.2,
        response_format: Literal["text", "json_object"] = "text",
        timeout_s: int = 30,
        request_id: str | None = None,
    ) -> LLMResponse:
        started = time.perf_counter()
        request_args = {
            "model": self.model,
            "messages": [{"role": item.role, "content": item.content} for item in messages],
            "max_tokens": max_output_tokens,
            "temperature": temperature,
            "timeout": timeout_s,
            "extra_headers": {"OpenAI-Beta": "no-training", "X-Request-ID": request_id or ""},
        }
        if response_format == "json_object":
            request_args["response_format"] = {"type": "json_object"}
        response = await self.client.chat.completions.create(**request_args)
        choice = response.choices[0]
        usage = response.usage
        return LLMResponse(
            text=choice.message.content or "",
            model=response.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            finish_reason=choice.finish_reason or "unknown",
            latency_ms=int((time.perf_counter() - started) * 1000),
            raw=response.model_dump(),
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        max_output_tokens: int = 1500,
        temperature: float = 0.2,
        timeout_s: int = 60,
        request_id: str | None = None,
    ) -> AsyncIterator[str]:
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": item.role, "content": item.content} for item in messages],
            max_tokens=max_output_tokens,
            temperature=temperature,
            stream=True,
            timeout=timeout_s,
            extra_headers={"OpenAI-Beta": "no-training", "X-Request-ID": request_id or ""},
        )
        async for event in stream:
            delta = event.choices[0].delta.content
            if delta:
                yield delta
