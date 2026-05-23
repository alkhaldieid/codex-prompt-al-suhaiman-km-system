from app.services.ingestion_progress import INGESTION_STAGES, INGESTION_TARGET_SECONDS


def test_upload_target_is_two_minutes() -> None:
    assert INGESTION_TARGET_SECONDS == 120


def test_progress_labels_are_arabic() -> None:
    assert all(any("\u0600" <= char <= "\u06ff" for char in stage.label_ar) for stage in INGESTION_STAGES)
