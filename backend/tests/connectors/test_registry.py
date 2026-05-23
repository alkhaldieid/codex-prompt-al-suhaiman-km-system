from app.connectors.registry import REGULATORY_SOURCES, get_regulatory_source, official_domains


def test_registry_has_core_production_sources() -> None:
    source_ids = {source.source_id for source in REGULATORY_SOURCES}
    assert {"boe_laws", "umm_al_qura", "sama", "cma", "zatca", "mhrsd", "sfda", "cst"}.issubset(
        source_ids
    )


def test_sources_have_official_domains_and_entrypoints() -> None:
    for source in REGULATORY_SOURCES:
        assert source.domains
        assert source.entrypoints
        assert all(domain.endswith(".gov.sa") or domain.endswith(".org.sa") for domain in source.domains)


def test_get_source_by_id() -> None:
    assert get_regulatory_source("boe_laws") is not None
    assert get_regulatory_source("missing") is None


def test_official_domains_include_known_sources() -> None:
    domains = official_domains()
    assert "laws.boe.gov.sa" in domains
    assert "portal.uqn.gov.sa" in domains
    assert "zatca.gov.sa" in domains
