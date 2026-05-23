from pathlib import Path
from uuid import UUID

from app.core.config import get_settings


class LocalObjectStorage:
    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or get_settings().storage_root)

    def put_raw(self, *, doc_id: UUID, filename: str, content: bytes) -> str:
        safe_name = Path(filename).name
        key = f"raw/{doc_id}/{safe_name}"
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return key


def get_storage() -> LocalObjectStorage:
    return LocalObjectStorage()
