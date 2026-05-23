from pathlib import Path

ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png", ".tiff", ".tif"}


def is_allowed_upload_filename(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_UPLOAD_EXTENSIONS
