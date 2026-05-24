from dataclasses import dataclass, field
from typing import Literal


@dataclass
class OpenAIDocumentPolicySubject:
    source_track: Literal["track1_external", "track2_legacy", "track3_capture", "synthetic"]
    privilege_flag: bool = False
    pii_flags: list[str] = field(default_factory=list)
    visibility: Literal["firm_wide", "practice_area_only", "restricted_matter", "owner_only"] = (
        "firm_wide"
    )


def can_send_to_openai(doc: OpenAIDocumentPolicySubject) -> tuple[bool, str | None]:
    if doc.source_track == "track2_legacy":
        return False, "track2"
    if doc.privilege_flag:
        return False, "privilege"
    if doc.pii_flags:
        return False, "pii"
    if doc.visibility == "restricted_matter":
        return False, "restricted_matter"
    return True, None


def subject_from_document(doc) -> OpenAIDocumentPolicySubject:
    """Build a policy subject from a Document ORM instance."""
    pii = doc.pii_flags
    if isinstance(pii, str):
        pii_list = [p for p in pii.split(",") if p]
    else:
        pii_list = list(pii or [])
    return OpenAIDocumentPolicySubject(
        source_track=doc.source_track.value
        if hasattr(doc.source_track, "value")
        else doc.source_track,
        privilege_flag=bool(doc.privilege_flag),
        pii_flags=pii_list,
        visibility=doc.visibility or "firm_wide",
    )

