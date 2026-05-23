import re


def normalize_arabic(text: str) -> str:
    normalized = text
    normalized = re.sub("[إأآٱ]", "ا", normalized)
    normalized = normalized.replace("ى", "ي")
    normalized = normalized.replace("ؤ", "و").replace("ئ", "ي")
    normalized = re.sub(r"[\u064b-\u065f\u0670ـ]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def chunk_text(text: str, *, target_chars: int = 1400, overlap_chars: int = 180) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= target_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(paragraph) <= target_chars:
            current = paragraph
            continue
        start = 0
        while start < len(paragraph):
            chunks.append(paragraph[start : start + target_chars].strip())
            start += target_chars - overlap_chars
        current = ""
    if current:
        chunks.append(current)
    return chunks
