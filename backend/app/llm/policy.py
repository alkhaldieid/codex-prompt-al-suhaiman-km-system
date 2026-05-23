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

