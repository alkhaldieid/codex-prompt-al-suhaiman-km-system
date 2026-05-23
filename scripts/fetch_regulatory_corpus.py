"""Fetch real Saudi law text from BOE for the PoC regulatory corpus.

Run from repo root:  python scripts/fetch_regulatory_corpus.py
Writes:
  fixtures/regulatory/<slug>.txt
  fixtures/regulatory/manifest.json
"""

import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "fixtures" / "regulatory"

BOE_BASE = "https://laws.boe.gov.sa"
USER_AGENT = "ETHKA-Suhaiman-KM/1.0 (+legal@ethka.dev)"

# Source-of-truth list. doc_type maps to the canonical enum in §3.1.
TARGETS = [
    {
        "slug": "civil_transactions_law",
        "guid": "655fdb42-8c96-422b-b8c4-b04f0095c94c",
        "title_ar": "نظام المعاملات المدنية",
        "doc_type": "regulation",
        "practice_area": ["corporate_commercial", "real_estate", "litigation_dispute"],
    },
    {
        "slug": "labor_law",
        "guid": "08381293-6388-48e2-8ad2-a9a700f2aa94",
        "title_ar": "نظام العمل",
        "doc_type": "regulation",
        "practice_area": ["labor_employment"],
    },
    {
        "slug": "pdpl",
        "guid": "b7cfae89-828e-4994-b167-adaa00e37188",
        "title_ar": "نظام حماية البيانات الشخصية",
        "doc_type": "regulation",
        "practice_area": ["regulatory_compliance"],
    },
    {
        "slug": "aml_law",
        "guid": "0657dfce-95f8-463a-9d87-aa3900ec7b51",
        "title_ar": "نظام مكافحة غسل الأموال",
        "doc_type": "regulation",
        "practice_area": ["banking_finance", "regulatory_compliance", "criminal"],
    },
    {
        "slug": "companies_law",
        "guid": "a8376aea-1bc3-49d4-9027-aed900b555af",
        "title_ar": "نظام الشركات",
        "doc_type": "regulation",
        "practice_area": ["corporate_commercial", "regulatory_compliance"],
    },
    {
        "slug": "commercial_courts_law",
        "guid": "38334008-3b70-4c6c-b3af-aba3016a8061",
        "title_ar": "نظام المحاكم التجارية",
        "doc_type": "regulation",
        "practice_area": ["litigation_dispute", "corporate_commercial"],
    },
]


def fetch_url(url: str, *, retries: int = 4, backoff: float = 2.0) -> bytes:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            req = Request(url, headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "ar,en;q=0.5",
                "From": "legal@ethka.dev",
            })
            with urlopen(req, timeout=45) as resp:
                return resp.read()
        except Exception as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(backoff ** attempt)
    raise RuntimeError(f"failed to fetch {url}: {last_exc}")


def extract_law_text(html: str) -> str:
    """BOE detail pages: strip scripts/styles/nav, return readable Arabic text."""
    # Drop scripts, styles, comments
    text = re.sub(r"<script[\s\S]*?</script>", " ", html)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text)
    text = re.sub(r"<!--[\s\S]*?-->", " ", text)

    # Keep paragraph/heading boundaries as line breaks
    text = re.sub(r"</(p|div|li|tr|h[1-6]|br)\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)

    # Drop all remaining tags
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)

    # Normalize whitespace per line; collapse blank-line runs to one
    lines = []
    for raw in text.splitlines():
        cleaned = re.sub(r"[ \t  -​]+", " ", raw).strip()
        lines.append(cleaned)
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def slice_law_body(text: str) -> str:
    """Trim BOE chrome around the law body using stable Arabic anchors.

    Keeps everything from the first occurrence of an article-style marker
    (المادة, الفصل, الباب, مرسوم ملكي) onward, dropping prior nav/breadcrumbs.
    Conservative — if no anchor is found, returns full cleaned text.
    """
    anchors = [
        "المادة الأولى",
        "المادة (الأولى)",
        "المادة ١",
        "المادة 1",
        "الباب الأول",
        "الفصل الأول",
        "مرسوم ملكي",
    ]
    earliest = len(text)
    for needle in anchors:
        idx = text.find(needle)
        if 0 <= idx < earliest:
            earliest = idx
    if earliest < len(text):
        return text[earliest:].strip()
    return text


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_base_url": BOE_BASE,
        "items": [],
    }
    failures: list[str] = []

    for target in TARGETS:
        url = f"{BOE_BASE}/BoeLaws/Laws/LawDetails/{target['guid']}/1"
        out_path = OUT_DIR / f"{target['slug']}.txt"
        print(f"[fetch] {target['slug']} <- {url}", flush=True)
        try:
            raw = fetch_url(url)
            html = raw.decode("utf-8", errors="replace")
            cleaned = extract_law_text(html)
            body = slice_law_body(cleaned)
            if len(body) < 1500:
                raise RuntimeError(f"suspiciously short body: {len(body)} chars")
            out_path.write_text(body, encoding="utf-8")
            sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
            manifest["items"].append({
                "slug": target["slug"],
                "title_ar": target["title_ar"],
                "doc_type": target["doc_type"],
                "practice_area": target["practice_area"],
                "source_url": url,
                "filename": out_path.name,
                "char_count": len(body),
                "sha256": sha,
            })
            print(f"        OK  {len(body):>7d} chars  sha={sha[:12]}", flush=True)
            # Polite pacing — BOE rate limit per spec §4.2 (6 rpm)
            time.sleep(12)
        except Exception as exc:  # noqa: BLE001
            print(f"        FAIL {exc}", flush=True)
            failures.append(f"{target['slug']}: {exc}")

    manifest_path = OUT_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nManifest written to {manifest_path}")
    print(f"Successful: {len(manifest['items'])}/{len(TARGETS)}")
    if failures:
        print("Failures:")
        for f in failures:
            print(f"  - {f}")

    # Brief required minimum: 3 of 5
    if len(manifest["items"]) < 3:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
