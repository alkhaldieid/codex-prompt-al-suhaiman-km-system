import base64
import time

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.ocr.base import OCRClient, OCRPage, OCRResponse


class OpenAIVisionOCRClient(OCRClient):
    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.ocr_model
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.llm_timeout_ms / 1000)

    async def extract_text(
        self,
        *,
        file_bytes: bytes,
        mime_type: str,
        filename: str,
        request_id: str | None = None,
    ) -> OCRResponse:
        started = time.perf_counter()
        encoded = base64.b64encode(file_bytes).decode("ascii")
        data_url = f"data:{mime_type};base64,{encoded}"
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "استخرج النص العربي من الصورة أو الصفحة المرفقة بدقة. "
                        "أعد النص فقط، محافظاً على ترتيب الفقرات والأرقام قدر الإمكان."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"اسم الملف: {filename}"},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            temperature=0,
            max_tokens=3000,
            timeout=60,
            extra_headers={"OpenAI-Beta": "no-training", "X-Request-ID": request_id or ""},
        )
        usage = response.usage
        text = response.choices[0].message.content or ""
        return OCRResponse(
            pages=[OCRPage(page_no=1, text=text, mean_confidence=None, blocks=[])],
            model=response.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            latency_ms=int((time.perf_counter() - started) * 1000),
            raw=response.model_dump(),
        )
