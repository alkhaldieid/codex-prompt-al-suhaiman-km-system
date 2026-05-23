import re

ARABIC_RE = re.compile(r"[\u0600-\u06ff]")
LATIN_NOISE_RE = re.compile(r"^(classification|strict|restricted|confidential)\b", re.IGNORECASE)
MARKER_ONLY_RE = re.compile(r"^[\s•▪o\-\–—·.،:;؛\(\)\[\]{}0-9٠-٩]+$")


def normalize_arabic(text: str) -> str:
    normalized = text
    normalized = re.sub("[إأآٱ]", "ا", normalized)
    normalized = normalized.replace("ى", "ي")
    normalized = normalized.replace("ؤ", "و").replace("ئ", "ي")
    normalized = re.sub(r"[\u064b-\u065f\u0670ـ]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def clean_extracted_text(text: str) -> str:
    lines = []
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        if LATIN_NOISE_RE.search(line):
            continue
        if MARKER_ONLY_RE.match(line):
            continue
        arabic_count = len(ARABIC_RE.findall(line))
        if arabic_count < 3 and len(line) < 40:
            continue
        lines.append(line)

    paragraphs: list[str] = []
    current = ""
    for line in lines:
        is_heading = len(line) <= 80 and not line.endswith((".", "؟", ":", "؛"))
        if is_heading:
            if current:
                paragraphs.append(current.strip())
            paragraphs.append(line)
            current = ""
            continue
        candidate = f"{current} {line}".strip() if current else line
        if len(candidate) > 900:
            paragraphs.append(current.strip())
            current = line
        else:
            current = candidate
    if current:
        paragraphs.append(current.strip())

    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)


def chunk_text(text: str, *, target_chars: int = 900, overlap_chars: int = 120) -> list[str]:
    clean_text = clean_extracted_text(text)
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", clean_text) if part.strip()]
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
