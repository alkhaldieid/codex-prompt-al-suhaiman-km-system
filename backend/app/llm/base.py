from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Literal


@dataclass
class LLMMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass
class LLMResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    finish_reason: str
    latency_ms: int
    raw: dict


class LLMClient(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        max_output_tokens: int = 1500,
        temperature: float = 0.2,
        response_format: Literal["text", "json_object"] = "text",
        timeout_s: int = 30,
        request_id: str | None = None,
    ) -> LLMResponse: ...

    @abstractmethod
    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        max_output_tokens: int = 1500,
        temperature: float = 0.2,
        timeout_s: int = 60,
        request_id: str | None = None,
    ) -> AsyncIterator[str]: ...
