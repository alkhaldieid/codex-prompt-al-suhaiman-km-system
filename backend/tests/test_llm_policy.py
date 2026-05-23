from app.llm.policy import OpenAIDocumentPolicySubject, can_send_to_openai


def test_blocks_privileged_documents() -> None:
    doc = OpenAIDocumentPolicySubject(source_track="synthetic", privilege_flag=True)
    assert can_send_to_openai(doc) == (False, "privilege")


def test_allows_public_synthetic_documents() -> None:
    doc = OpenAIDocumentPolicySubject(source_track="synthetic")
    assert can_send_to_openai(doc) == (True, None)


def test_blocks_track2_for_all_openai_surfaces() -> None:
    doc = OpenAIDocumentPolicySubject(source_track="track2_legacy")
    assert can_send_to_openai(doc) == (False, "track2")
