from app.services.retrieval import tokenize_query


def test_tokenize_query_normalizes_arabic() -> None:
    assert "العمل" in tokenize_query("نظام العمل")
