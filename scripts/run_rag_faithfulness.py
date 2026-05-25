"""RAG faithfulness evaluator (spec §7.5 + §14.4).

For each Q/A pair:
  1. Send the question to /search/ask via the running backend.
  2. Score the answer as faithful if BOTH:
     - At least one citation points to the expected document.
     - The answer mentions at least one of the must_mention_any terms.
  3. Pass if citation precision >= 0.90.

To keep the eval cheap (no separate LLM judge), we use a deterministic
keyword + citation-match rubric. The expected_doc_id is the law slug
UUID we know contains the answer; the must_mention_any list anchors
the answer in real legal terms from the law text.

Usage:
  python scripts/run_rag_faithfulness.py
  python scripts/run_rag_faithfulness.py --limit 5     # smoke
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH = REPO / "evals" / "benchmarks" / "rag_faithfulness.json"

THRESHOLD = 0.90


def login(api_base: str) -> str:
    body = json.dumps({"email": "lawyer.a@demo.suhaiman.sa", "password": "DemoPass123!"}).encode()
    req = urllib.request.Request(
        f"{api_base}/api/v1/auth/login",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())["access_token"]


def ask(api_base: str, token: str, question: str) -> dict:
    body = json.dumps({"question": question}).encode()
    req = urllib.request.Request(
        f"{api_base}/api/v1/search/ask",
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def evaluate_pair(item: dict, response: dict) -> tuple[bool, str]:
    if response.get("refused"):
        return False, f"refused: {response.get('refusal_reason')}"
    answer = response.get("answer_ar", "") or ""
    citations = response.get("citations", []) or []
    # Accept either a single canonical doc (expected_doc_id) or a set of
    # acceptable docs (acceptable_doc_ids). The Saudi procedural-justice
    # corpus has overlapping laws (Sharia Procedure ↔ Commercial Courts,
    # Criminal Procedure ↔ Appellate Procedure ↔ Public Defender) where
    # multiple sources can be faithful answers to one question.
    acceptable = set(item.get("acceptable_doc_ids") or [])
    if item.get("expected_doc_id"):
        acceptable.add(item["expected_doc_id"])
    cited_docs = {c.get("doc_id") for c in citations}
    if not (acceptable & cited_docs):
        return False, f"no citation to any acceptable doc {sorted(acceptable)}; cited: {cited_docs}"
    needles = item.get("must_mention_any", [])
    if needles and not any(n in answer for n in needles):
        return False, f"no must-mention term in answer (looked for {needles})"
    return True, "ok"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=os.environ.get("API_BASE", "http://localhost:8000"))
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    items = json.loads(BENCH.read_text(encoding="utf-8"))
    if args.limit:
        items = items[: args.limit]

    print(f"Faithfulness eval — {len(items)} pairs against {args.api}")
    token = login(args.api)

    passed = 0
    failures = []
    for item in items:
        try:
            resp = ask(args.api, token, item["question"])
        except Exception as exc:  # noqa: BLE001
            print(f"  [FAIL] q{item['id']:>2}  upstream: {exc}")
            failures.append({"id": item["id"], "reason": str(exc)})
            continue
        ok, reason = evaluate_pair(item, resp)
        flag = "PASS" if ok else "FAIL"
        latency = resp.get("took_ms", "?")
        print(f"  [{flag}] q{item['id']:>2}  took={latency}ms  {item['question'][:60]}")
        if ok:
            passed += 1
        else:
            print(f"         reason: {reason}")
            failures.append({"id": item["id"], "reason": reason, "answer": (resp.get("answer_ar") or "")[:200]})

    n = len(items)
    precision = passed / n if n else 0.0
    print(f"\nCitation+keyword precision: {precision:.3f}  (threshold {THRESHOLD})")
    print(f"Passed: {passed}/{n}")
    if failures:
        print("Failures:")
        for f in failures:
            print(f"  q{f['id']}: {f['reason']}")
    if precision < THRESHOLD:
        print("\nFaithfulness gate FAILED")
        return 1
    print("\nFaithfulness gate PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
