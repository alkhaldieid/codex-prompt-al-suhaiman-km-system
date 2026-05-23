from app.services.text_processing import chunk_text, normalize_arabic


def test_normalize_arabic_removes_diacritics_and_unifies_alef() -> None:
    assert normalize_arabic("إخلالٌ جوهريّ") == "اخلال جوهري"


def test_chunk_text_splits_long_paragraphs() -> None:
    chunks = chunk_text("أ" * 3000, target_chars=1000, overlap_chars=100)
    assert len(chunks) >= 3
