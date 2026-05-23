from app.llm.policy import LLMDocumentPolicySubject, can_send_to_external_llm


def test_blocks_privileged_documents() -> None:
    doc = LLMDocumentPolicySubject(source_track="synthetic", privilege_flag=True)
    assert can_send_to_external_llm(doc) == (False, "privilege")


def test_allows_public_synthetic_documents() -> None:
    doc = LLMDocumentPolicySubject(source_track="synthetic")
    assert can_send_to_external_llm(doc) == (True, None)
