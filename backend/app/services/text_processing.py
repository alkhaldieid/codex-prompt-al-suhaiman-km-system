import re

ARABIC_RE = re.compile(r"[؀-ۿ]")
LATIN_NOISE_RE = re.compile(r"^(classification|strict|restricted|confidential)\b", re.IGNORECASE)
MARKER_ONLY_RE = re.compile(r"^[\s•▪o\-\–—·.،:;؛\(\)\[\]{}0-9٠-٩]+$")

# Spec §6.1: Arabic legal citation markers must stay attached to their
# referenced number/letter. Match against normalized whitespace.
ARTICLE_MARKER_RE = re.compile(
    r"(المادة|الفقرة|البند|الفصل|الباب)\s+("
    r"[٠-٩0-9]+|"
    r"\([٠-٩0-9]+\)|"
    r"الأولى|الثانية|الثالثة|الرابعة|الخامسة|السادسة|السابعة|الثامنة|التاسعة|العاشرة|"
    r"الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر"
    r")"
)


def normalize_arabic(text: str) -> str:
    normalized = text
    normalized = re.sub("[إأآٱ]", "ا", normalized)
    normalized = normalized.replace("ى", "ي")
    normalized = normalized.replace("ؤ", "و").replace("ئ", "ي")
    normalized = re.sub(r"[ً-ٰٟـ]", "", normalized)
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


def _split_into_articles(text: str) -> list[str]:
    """Split a law-text blob on article markers, keeping each marker attached
    to its body. If no markers found, returns the whole text as one block.
    """
    # Find positions of each marker so we can slice between them
    positions = [m.start() for m in ARTICLE_MARKER_RE.finditer(text)]
    if len(positions) < 2:
        return [text.strip()] if text.strip() else []
    blocks: list[str] = []
    # Preamble (anything before the first marker)
    if positions[0] > 0:
        head = text[: positions[0]].strip()
        if head:
            blocks.append(head)
    # Each article: from its marker to the next marker
    positions.append(len(text))
    for i in range(len(positions) - 1):
        chunk = text[positions[i] : positions[i + 1]].strip()
        if chunk:
            blocks.append(chunk)
    return blocks


def chunk_text(
    text: str,
    *,
    target_chars: int = 1600,
    max_chars: int = 2400,
    overlap_chars: int = 240,
) -> list[str]:
    """Paragraph-aware chunker per spec §6.1.

    Targets ~400–600 tokens (Arabic ≈ 3 chars/token → 1200–1800 chars). Max
    ~800 tokens (~2400 chars). Article markers (المادة/الفقرة/البند) and
    their numbers are kept atomic — chunk boundaries fall between articles,
    not inside them. Falls back to char-window splitting only for single
    articles longer than max_chars.
    """
    clean = clean_extracted_text(text)
    if not clean:
        return []

    blocks: list[str] = []
    # Split first on double-newline (paragraph breaks); within each paragraph,
    # split further on article markers if present.
    for paragraph in (p.strip() for p in re.split(r"\n{2,}", clean) if p.strip()):
        blocks.extend(_split_into_articles(paragraph))

    chunks: list[str] = []
    current = ""
    for block in blocks:
        candidate = f"{current}\n\n{block}".strip() if current else block
        if len(candidate) <= target_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(block) <= max_chars:
            current = block
            continue
        # Single block too large for max_chars (rare — usually only when a
        # law's preamble has no article structure). Fall back to a
        # char-window split with overlap, preserving overlap so citations
        # don't get cut.
        start = 0
        while start < len(block):
            piece = block[start : start + target_chars].strip()
            if piece:
                chunks.append(piece)
            start += target_chars - overlap_chars
    if current:
        chunks.append(current)
    return chunks
