from app.services.text_processing import clean_extracted_text, chunk_text, normalize_arabic


def test_normalize_arabic_removes_diacritics_and_unifies_alef() -> None:
    assert normalize_arabic("إخلالٌ جوهريّ") == "اخلال جوهري"


def test_chunk_text_splits_long_paragraphs() -> None:
    chunks = chunk_text("أ" * 3000, target_chars=1000, overlap_chars=100)
    assert len(chunks) >= 3


def test_clean_extracted_text_removes_layout_noise() -> None:
    raw = """
    Classification: Strict مقيد
    •
    •
    اللائحة التنفيذية
    لنظام العمل
    1.
    ملحق رقم 1)
    النموذج الموحد للائحة تنظيم العمل
    """
    clean = clean_extracted_text(raw)
    assert "Classification" not in clean
    assert "•" not in clean
    assert "اللائحة التنفيذية" in clean
    assert "النموذج الموحد" in clean
