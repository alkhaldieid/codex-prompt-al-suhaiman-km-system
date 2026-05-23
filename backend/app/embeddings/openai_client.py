import time

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.embeddings.base import EmbeddingResponse, EmbeddingsClient


class OpenAIEmbeddingsClient(EmbeddingsClient):
    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.embeddings_model
        self.dimensions = settings.embeddings_dimensions
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.llm_timeout_ms / 1000)

    async def embed_texts(
        self,
        texts: list[str],
        *,
        request_id: str | None = None,
    ) -> EmbeddingResponse:
        started = time.perf_counter()
        response = await self.client.embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimensions,
            extra_headers={"OpenAI-Beta": "no-training", "X-Request-ID": request_id or ""},
        )
        usage = response.usage
        return EmbeddingResponse(
            vectors=[item.embedding for item in response.data],
            model=response.model,
            dimensions=self.dimensions,
            input_tokens=usage.prompt_tokens if usage else 0,
            latency_ms=int((time.perf_counter() - started) * 1000),
            raw=response.model_dump(),
        )
