"""Rewrite evals/benchmarks/*.json expected_doc_ids using the live DB.

Why this exists:
  Document IDs in the seeded corpus come from the connector (MoJ today,
  potentially others later). Each connector picks its own doc IDs —
  uuid4 from MoJ, deterministic uuid5 from the old BOE seed. So whenever
  the corpus is regenerated (e.g. `docker compose down -v && up -d`),
  the expected_doc_ids in our benchmark JSON files need updating.

How:
  - Each benchmark item carries a `notes` field describing which law(s)
    it should match (free-form, in English).
  - This script keeps an in-script keyword→title-substring lookup, so
    e.g. "Evidence Law" → "نظام الإثبات" finds the right MoJ doc.
  - For each item, it resolves notes → title substring → live doc_id,
    then writes the doc_id back into the JSON file.
  - If a lookup fails, it prints the failure and *skips* the item
    (drops it from the output) — never silently writes a wrong UUID.

The connector-corpus reality:
  MoJ ships procedural-justice statutes (الإثبات, المحاكم التجارية,
  المرافعات الشرعية, التوثيق, التسجيل العيني للعقار, …) rather than
  the BOE substantive-law set (PDPL, AML, Companies, Labor). The
  current benchmarks target the procedural set. If you change the
  corpus, add new keyword→title entries below.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DB_URL = "postgresql://suhaiman:suhaiman@localhost:5432/suhaiman_km"

BENCHMARKS = [
    REPO / "evals" / "benchmarks" / "search_queries.json",
    REPO / "evals" / "benchmarks" / "rag_faithfulness.json",
]

# Free-form English (notes-field) keyword → Arabic title substring.
# Match order matters: more specific keywords first.
LOOKUP: list[tuple[str, str]] = [
    ("Evidence Law", "نظام الإثبات"),
    ("Commercial Courts Law", "نظام المحاكم التجارية"),
    ("Sharia Procedure Law", "نظام المرافعات الشرعية"),
    ("Sharia Procedure Implementing", "اللوائح التنفيذية لنظام المرافعات الشرعية"),
    ("Notarization Implementing", "اللائحة التنفيذية لنظام التوثيق"),
    ("Notarization Law", "نظام التوثيق"),
    ("Real Estate Registration", "نظام التسجيل العيني للعقار"),
    ("Real Estate Mortgage", "نظام الرهن العقاري المسجل"),
    ("Real Estate Finance", "نظام التمويل العقاري"),
    ("Condominium", "نظام ملكية الوحدات العقارية"),
    ("Expropriation", "نظام نزع ملكية العقارات"),
    ("Juveniles Law", "نظام الأحداث"),
    ("Counter-Terrorism", "نظام مكافحة جرائم الإرهاب"),
    ("Lawyer Code", "قواعد السلوك المهني للمحامين"),
    ("Public Defender", "آلية الاستعانة بمحام"),
    ("Enforcement Implementing", "اللائحة التنفيذية لنظام التنفيذ"),
    ("Criminal Procedure Implementing", "اللائحة التنفيذية لنظام الإجراءات الجزائية"),
    ("Appellate Procedure Implementing", "اللائحة التنفيذية لإجراءات الاستئناف"),
    ("Maintenance Fund", "تنظيم صندوق النفقة"),
    ("Conciliation Center", "تنظيم مركز المصالحة"),
    ("Conciliation Office", "قواعد العمل في مكاتب المصالحة"),
    ("Bankruptcy Expert Fees", "قواعد تحديد أتعاب الخبراء"),
    ("Lessor Asset Recovery", "ضوابط تسلم المؤجر"),
    ("Common Property Division", "لائحة قسمة الأموال المشتركة"),
    ("E-Litigation Manual", "الدليل الإجرائي لخدمة التقاضي الإلكتروني"),
]


def _resolve_keywords(notes: str) -> list[str]:
    """Return title substrings whose keyword appears in the notes string."""
    hits = []
    for keyword, title_sub in LOOKUP:
        if keyword.lower() in notes.lower():
            hits.append(title_sub)
    return hits


def _lookup_doc_id(cur, title_sub: str) -> str | None:
    cur.execute(
        "SELECT doc_id::text FROM documents WHERE title_ar LIKE %s LIMIT 1",
        (f"%{title_sub}%",),
    )
    row = cur.fetchone()
    return row[0] if row else None


def _process_file(cur, path: Path) -> tuple[int, int]:
    """Rewrite path in place. Returns (kept, dropped)."""
    items = json.loads(path.read_text(encoding="utf-8"))
    rewritten = []
    dropped = 0
    for item in items:
        notes = item.get("notes") or ""
        title_subs = _resolve_keywords(notes)
        if not title_subs:
            print(f"  [DROP {path.name} #{item.get('id')}] no keyword match in notes: {notes!r}")
            dropped += 1
            continue
        ids = []
        unresolved = []
        for sub in title_subs:
            doc_id = _lookup_doc_id(cur, sub)
            if doc_id:
                ids.append(doc_id)
            else:
                unresolved.append(sub)
        if not ids:
            print(
                f"  [DROP {path.name} #{item.get('id')}] no DB match for "
                f"{title_subs!r}; notes={notes!r}"
            )
            dropped += 1
            continue
        if unresolved:
            print(
                f"  [PARTIAL {path.name} #{item.get('id')}] kept {ids}, "
                f"dropped unresolvable {unresolved}"
            )
        # search_queries.json uses expected_top10 (list);
        # rag_faithfulness.json uses expected_doc_id (single primary,
        # optional acceptable_doc_ids for procedural cross-references).
        if "expected_top10" in item or path.name == "search_queries.json":
            item["expected_top10"] = ids
            item.pop("expected_top3", None)
        else:
            item["expected_doc_id"] = ids[0]
            if len(ids) > 1 or "acceptable_doc_ids" in item:
                item["acceptable_doc_ids"] = ids
        rewritten.append(item)
    path.write_text(json.dumps(rewritten, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(rewritten), dropped


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", DEFAULT_DB_URL),
    )
    args = parser.parse_args()
    db_url = args.database_url.replace("postgresql+psycopg://", "postgresql://")

    total_kept = 0
    total_dropped = 0
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            for path in BENCHMARKS:
                if not path.exists():
                    print(f"  [SKIP] {path} not present")
                    continue
                print(f"\n== {path.name} ==")
                kept, dropped = _process_file(cur, path)
                total_kept += kept
                total_dropped += dropped
                print(f"  -> kept {kept}, dropped {dropped}")

    print(f"\nDone. Total: {total_kept} kept, {total_dropped} dropped.")
    return 0 if total_kept > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
