from dataclasses import dataclass
from typing import Literal


IngestionStageKey = Literal["uploading", "ocr", "metadata", "indexing", "done"]


@dataclass(frozen=True)
class IngestionStage:
    key: IngestionStageKey
    label_ar: str
    order: int


INGESTION_TARGET_SECONDS = 120

INGESTION_STAGES = [
    IngestionStage(key="uploading", label_ar="جاري الرفع…", order=1),
    IngestionStage(key="ocr", label_ar="قراءة المستند ضوئياً…", order=2),
    IngestionStage(key="metadata", label_ar="استخلاص البيانات…", order=3),
    IngestionStage(key="indexing", label_ar="الفهرسة…", order=4),
    IngestionStage(key="done", label_ar="اكتملت المعالجة — جاهز للمراجعة", order=5),
]
