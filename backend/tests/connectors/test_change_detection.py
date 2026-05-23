from app.connectors.change_detection import detect_change, fingerprint_content


def test_new_fingerprint_emits_change_event() -> None:
    current = fingerprint_content(source_id="boe_laws", url="https://laws.boe.gov.sa", content=b"a")
    event = detect_change(None, current)
    assert event is not None
    assert event.reason == "new_source_item"


def test_changed_content_hash_emits_change_event() -> None:
    previous = fingerprint_content(source_id="boe_laws", url="https://laws.boe.gov.sa", content=b"a")
    current = fingerprint_content(source_id="boe_laws", url="https://laws.boe.gov.sa", content=b"b")
    event = detect_change(previous, current)
    assert event is not None
    assert event.reason == "content_hash_changed"


def test_unchanged_fingerprint_emits_no_event() -> None:
    previous = fingerprint_content(source_id="boe_laws", url="https://laws.boe.gov.sa", content=b"a")
    current = fingerprint_content(source_id="boe_laws", url="https://laws.boe.gov.sa", content=b"a")
    assert detect_change(previous, current) is None
