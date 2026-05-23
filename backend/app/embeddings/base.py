from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class EmbeddingResponse:
    vectors: list[list[float]]
    model: str
    dimensions: int
    input_tokens: int
    latency_ms: int
    raw: dict


class EmbeddingsClient(ABC):
    @abstractmethod
    async def embed_texts(
        self,
        texts: list[str],
        *,
        request_id: str | None = None,
    ) -> EmbeddingResponse: ...
