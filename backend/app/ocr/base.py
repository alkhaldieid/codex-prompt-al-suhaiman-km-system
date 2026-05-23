from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class OCRPage:
    page_no: int
    text: str
    mean_confidence: float | None = None
    blocks: list[dict] = field(default_factory=list)


@dataclass
class OCRResponse:
    pages: list[OCRPage]
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    raw: dict


class OCRClient(ABC):
    @abstractmethod
    async def extract_text(
        self,
        *,
        file_bytes: bytes,
        mime_type: str,
        filename: str,
        request_id: str | None = None,
    ) -> OCRResponse: ...
