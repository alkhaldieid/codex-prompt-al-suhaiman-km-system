import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class SourceFingerprint:
    source_id: str
    url: str
    content_sha256: str
    etag: str | None = None
    last_modified: str | None = None
    checked_at: datetime | None = None


@dataclass(frozen=True)
class SourceChangeEvent:
    source_id: str
    url: str
    reason: str
    previous_sha256: str | None
    current_sha256: str
    detected_at: datetime


def fingerprint_content(
    *,
    source_id: str,
    url: str,
    content: bytes,
    etag: str | None = None,
    last_modified: str | None = None,
) -> SourceFingerprint:
    return SourceFingerprint(
        source_id=source_id,
        url=url,
        content_sha256=hashlib.sha256(content).hexdigest(),
        etag=etag,
        last_modified=last_modified,
        checked_at=datetime.now(timezone.utc),
    )


def detect_change(
    previous: SourceFingerprint | None,
    current: SourceFingerprint,
) -> SourceChangeEvent | None:
    if previous is None:
        return SourceChangeEvent(
            source_id=current.source_id,
            url=current.url,
            reason="new_source_item",
            previous_sha256=None,
            current_sha256=current.content_sha256,
            detected_at=current.checked_at or datetime.now(timezone.utc),
        )
    if previous.content_sha256 != current.content_sha256:
        return SourceChangeEvent(
            source_id=current.source_id,
            url=current.url,
            reason="content_hash_changed",
            previous_sha256=previous.content_sha256,
            current_sha256=current.content_sha256,
            detected_at=current.checked_at or datetime.now(timezone.utc),
        )
    if previous.etag and current.etag and previous.etag != current.etag:
        return SourceChangeEvent(
            source_id=current.source_id,
            url=current.url,
            reason="etag_changed",
            previous_sha256=previous.content_sha256,
            current_sha256=current.content_sha256,
            detected_at=current.checked_at or datetime.now(timezone.utc),
        )
    if previous.last_modified and current.last_modified and previous.last_modified != current.last_modified:
        return SourceChangeEvent(
            source_id=current.source_id,
            url=current.url,
            reason="last_modified_changed",
            previous_sha256=previous.content_sha256,
            current_sha256=current.content_sha256,
            detected_at=current.checked_at or datetime.now(timezone.utc),
        )
    return None
