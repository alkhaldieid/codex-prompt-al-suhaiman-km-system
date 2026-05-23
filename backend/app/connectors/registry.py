from dataclasses import dataclass
from enum import Enum


class SourceType(str, Enum):
    canonical_law_database = "canonical_law_database"
    official_gazette = "official_gazette"
    regulator_rules = "regulator_rules"
    consultation_drafts = "consultation_drafts"
    ministry_rules = "ministry_rules"
    national_aggregator = "national_aggregator"


class UpdateStrategy(str, Enum):
    feed_or_api = "feed_or_api"
    sitemap_or_index_diff = "sitemap_or_index_diff"
    html_list_diff = "html_list_diff"
    pdf_manifest_diff = "pdf_manifest_diff"
    head_etag_last_modified = "head_etag_last_modified"


@dataclass(frozen=True)
class RegulatorySource:
    source_id: str
    name_ar: str
    name_en: str
    domains: tuple[str, ...]
    entrypoints: tuple[str, ...]
    source_type: SourceType
    practice_domains: tuple[str, ...]
    update_strategies: tuple[UpdateStrategy, ...]
    priority: int
    robots_required: bool = True
    event_driven_capable: bool = True


REGULATORY_SOURCES: tuple[RegulatorySource, ...] = (
    RegulatorySource(
        source_id="boe_laws",
        name_ar="هيئة الخبراء بمجلس الوزراء - الوثائق النظامية",
        name_en="Bureau of Experts laws database",
        domains=("laws.boe.gov.sa",),
        entrypoints=("https://laws.boe.gov.sa/BoeLaws/Laws/",),
        source_type=SourceType.canonical_law_database,
        practice_domains=("all",),
        update_strategies=(UpdateStrategy.html_list_diff, UpdateStrategy.head_etag_last_modified),
        priority=1,
    ),
    RegulatorySource(
        source_id="umm_al_qura",
        name_ar="جريدة أم القرى - الجريدة الرسمية",
        name_en="Umm Al-Qura official gazette",
        domains=("uqn.gov.sa", "portal.uqn.gov.sa"),
        entrypoints=("https://portal.uqn.gov.sa/DecisionsAndSystems", "https://www.uqn.gov.sa/"),
        source_type=SourceType.official_gazette,
        practice_domains=("all",),
        update_strategies=(UpdateStrategy.html_list_diff, UpdateStrategy.pdf_manifest_diff),
        priority=1,
    ),
    RegulatorySource(
        source_id="national_platform_rules",
        name_ar="المنصة الوطنية الموحدة - الأنظمة واللوائح",
        name_en="National Platform rules index",
        domains=("my.gov.sa",),
        entrypoints=("https://my.gov.sa/ar/rules", "https://my.gov.sa/en/rules"),
        source_type=SourceType.national_aggregator,
        practice_domains=("all",),
        update_strategies=(UpdateStrategy.html_list_diff,),
        priority=2,
    ),
    RegulatorySource(
        source_id="istitlaa",
        name_ar="منصة استطلاع - مشروعات الأنظمة واللوائح",
        name_en="Istitlaa public consultation drafts",
        domains=("istitlaa.ncc.gov.sa",),
        entrypoints=("https://istitlaa.ncc.gov.sa/ar", "https://istitlaa.ncc.gov.sa/en"),
        source_type=SourceType.consultation_drafts,
        practice_domains=("draft_regulations", "economic_development"),
        update_strategies=(UpdateStrategy.html_list_diff,),
        priority=2,
    ),
    RegulatorySource(
        source_id="sama",
        name_ar="البنك المركزي السعودي",
        name_en="Saudi Central Bank",
        domains=("sama.gov.sa", "www.sama.gov.sa"),
        entrypoints=("https://www.sama.gov.sa/ar-sa/News/Pages/default.aspx",),
        source_type=SourceType.regulator_rules,
        practice_domains=("banking_finance", "insurance", "payments", "aml"),
        update_strategies=(UpdateStrategy.html_list_diff, UpdateStrategy.head_etag_last_modified),
        priority=1,
    ),
    RegulatorySource(
        source_id="cma",
        name_ar="هيئة السوق المالية",
        name_en="Capital Market Authority",
        domains=("cma.gov.sa", "cma.org.sa"),
        entrypoints=("https://cma.gov.sa/ar/RulesRegulations/Regulations/Pages/default.aspx",),
        source_type=SourceType.regulator_rules,
        practice_domains=("capital_markets", "corporate_governance", "securities"),
        update_strategies=(UpdateStrategy.html_list_diff, UpdateStrategy.pdf_manifest_diff),
        priority=1,
    ),
    RegulatorySource(
        source_id="zatca",
        name_ar="هيئة الزكاة والضريبة والجمارك",
        name_en="Zakat, Tax and Customs Authority",
        domains=("zatca.gov.sa", "www.zatca.gov.sa"),
        entrypoints=("https://zatca.gov.sa/ar/RulesRegulations/Pages/systems.aspx",),
        source_type=SourceType.regulator_rules,
        practice_domains=("tax_zakat", "customs", "vat", "e_invoicing"),
        update_strategies=(UpdateStrategy.html_list_diff, UpdateStrategy.pdf_manifest_diff),
        priority=1,
    ),
    RegulatorySource(
        source_id="mhrsd",
        name_ar="وزارة الموارد البشرية والتنمية الاجتماعية",
        name_en="Ministry of Human Resources and Social Development",
        domains=("hrsd.gov.sa", "www.hrsd.gov.sa"),
        entrypoints=("https://www.hrsd.gov.sa/ar", "https://www.hrsd.gov.sa/en"),
        source_type=SourceType.ministry_rules,
        practice_domains=("labor_employment", "social_development"),
        update_strategies=(UpdateStrategy.sitemap_or_index_diff, UpdateStrategy.pdf_manifest_diff),
        priority=1,
    ),
    RegulatorySource(
        source_id="mc",
        name_ar="وزارة التجارة",
        name_en="Ministry of Commerce",
        domains=("mc.gov.sa", "www.mc.gov.sa"),
        entrypoints=("https://mc.gov.sa/ar", "https://mc.gov.sa/en"),
        source_type=SourceType.ministry_rules,
        practice_domains=("commerce", "companies", "consumer_protection", "franchise"),
        update_strategies=(UpdateStrategy.sitemap_or_index_diff, UpdateStrategy.html_list_diff),
        priority=2,
    ),
    RegulatorySource(
        source_id="sfda",
        name_ar="الهيئة العامة للغذاء والدواء",
        name_en="Saudi Food and Drug Authority",
        domains=("sfda.gov.sa", "www.sfda.gov.sa"),
        entrypoints=("https://www.sfda.gov.sa/ar/regulations", "https://www.sfda.gov.sa/en/regulations"),
        source_type=SourceType.regulator_rules,
        practice_domains=("food", "drugs", "medical_devices", "cosmetics"),
        update_strategies=(UpdateStrategy.html_list_diff, UpdateStrategy.pdf_manifest_diff),
        priority=2,
    ),
    RegulatorySource(
        source_id="cst",
        name_ar="هيئة الاتصالات والفضاء والتقنية",
        name_en="Communications, Space and Technology Commission",
        domains=("cst.gov.sa", "www.cst.gov.sa"),
        entrypoints=("https://www.cst.gov.sa/ar", "https://www.cst.gov.sa/en"),
        source_type=SourceType.regulator_rules,
        practice_domains=("telecom", "technology", "space", "postal", "digital_platforms"),
        update_strategies=(UpdateStrategy.sitemap_or_index_diff, UpdateStrategy.pdf_manifest_diff),
        priority=2,
    ),
    RegulatorySource(
        source_id="sdaia_dgp",
        name_ar="سدايا - مكتب إدارة البيانات الوطنية",
        name_en="SDAIA / National Data Governance",
        domains=("sdaia.gov.sa", "dgp.sdaia.gov.sa"),
        entrypoints=("https://sdaia.gov.sa", "https://dgp.sdaia.gov.sa"),
        source_type=SourceType.regulator_rules,
        practice_domains=("data_protection", "data_governance", "ai_governance"),
        update_strategies=(UpdateStrategy.sitemap_or_index_diff, UpdateStrategy.pdf_manifest_diff),
        priority=2,
    ),
)


def get_regulatory_source(source_id: str) -> RegulatorySource | None:
    return next((source for source in REGULATORY_SOURCES if source.source_id == source_id), None)


def official_domains() -> set[str]:
    return {domain for source in REGULATORY_SOURCES for domain in source.domains}
