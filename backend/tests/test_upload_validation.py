from app.services.upload_validation import is_allowed_upload_filename


def test_allowed_upload_extensions() -> None:
    assert is_allowed_upload_filename("حكم_تجاري.pdf")
    assert is_allowed_upload_filename("صورة.PNG")
    assert is_allowed_upload_filename("مذكرة.docx")


def test_rejects_unsupported_upload_extension() -> None:
    assert not is_allowed_upload_filename("archive.zip")
