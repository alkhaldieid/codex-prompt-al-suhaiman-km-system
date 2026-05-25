"""Corpus integrity gate.

Scans every row in document_chunks for known BOE-chrome contamination
strings. Exits non-zero (and prints each offending chunk) if any match
is found. Wired into CI as a PR-blocking job so contaminated text
cannot land on main.

The patterns are the ones that escaped the original cleanup pass:
  - comment-form labels (البريد الإلكتروني, رمز التحقق, الإسم/رقم الجوال)
  - the disclaimer block (إخلاء مسؤولية, تم إضافة البلاغ)
  - bookkeeping noise (اضافة تعديل حذف, أبلغني حين توافر)
  - safety nets for any JS/HTML accidentally captured (Loading..., <script, function ( ))

Usage:
  python3 scripts/run_corpus_integrity.py
  python3 scripts/run_corpus_integrity.py --database-url postgresql://...

By default it reads DATABASE_URL from the environment, falling back to
the docker-compose dev URL on localhost:5432.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

import psycopg


DEFAULT_DB_URL = "postgresql://suhaiman:suhaiman@localhost:5432/suhaiman_km"

# Each entry is (regex_pattern, human_label).
# IMPORTANT: do NOT add single-term patterns for vocabulary that appears
# in legitimate statute text. "البريد الإلكتروني" is used inside Saudi
# evidence law, notification provisions, AML KYC clauses, etc. — the
# contamination signal is the *context* (e.g. it being preceded by
# "الإسم" because BOE's portal renders both as adjacent form labels),
# not the term itself.
PATTERNS: list[tuple[str, str]] = [
    (r"الإسم\s+البريد الإلكتروني", "BOE comment-form label sequence"),
    (r"رمز التحقق", "CAPTCHA chrome"),
    (r"إخلاء مسؤولية", "disclaimer block"),
    (r"اضافة تعديل حذف", "navigation noise"),
    (r"أبلغني حين توافر", "navigation noise"),
    (r"تم إضافة البلاغ", "disclaimer: تم إضافة البلاغ"),
    (r"Loading\.\.\.", "loading state"),
    (r"<script", "raw HTML script tag"),
    (r"function\s*\(", "raw JS function literal"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", DEFAULT_DB_URL),
        help="Postgres URL (default: env DATABASE_URL or local dev)",
    )
    args = parser.parse_args()

    # SQLAlchemy-style URL prefixes won't work with raw psycopg.
    db_url = args.database_url.replace("postgresql+psycopg://", "postgresql://")

    failures: list[tuple[str, str, str, str]] = []
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT dc.chunk_id::text, dc.text_ar, d.title_ar
                FROM document_chunks dc
                JOIN documents d ON d.doc_id = dc.doc_id
                """
            )
            rows = cur.fetchall()

    compiled = [(re.compile(p), label) for p, label in PATTERNS]
    for chunk_id, text_ar, title_ar in rows:
        for rx, label in compiled:
            m = rx.search(text_ar)
            if m:
                snippet = text_ar[max(0, m.start() - 30) : m.end() + 60].replace("\n", " ")
                failures.append((title_ar, chunk_id, label, snippet))
                break  # one match per chunk is enough

    if not failures:
        print(f"Corpus integrity OK — scanned {len(rows)} chunks, 0 contaminations.")
        return 0

    print(f"Corpus integrity FAILED — {len(failures)} chunks contaminated out of {len(rows)}:\n")
    for title, chunk_id, label, snippet in failures[:50]:
        print(f"  [{label}]")
        print(f"    title:    {title}")
        print(f"    chunk_id: {chunk_id}")
        print(f"    snippet:  …{snippet}…")
        print()
    if len(failures) > 50:
        print(f"  …and {len(failures) - 50} more.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
