"""Real AI quality evaluator (replaces the placeholder-pass shim).

Hits the running backend's /api/v1/search endpoint with each benchmark
query, computes Recall@10 and MRR against the expected doc IDs, and
exits non-zero if thresholds fail.

Smoke mode (default): first 5 queries. Full mode: all 20.

Usage:
  python scripts/run_ai_quality.py --mode smoke
  python scripts/run_ai_quality.py --mode full --api http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH = REPO / "evals" / "benchmarks" / "search_queries.json"

# §1.2 T5 thresholds.
RECALL_AT_10_THRESHOLD = 0.80
MRR_THRESHOLD = 0.60


def login(api_base: str) -> str:
    body = json.dumps({"email": "lawyer.a@demo.suhaiman.sa", "password": "DemoPass123!"}).encode()
    req = urllib.request.Request(
        f"{api_base}/api/v1/auth/login",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["access_token"]


def search(api_base: str, token: str, query: str) -> list[dict]:
    url = f"{api_base}/api/v1/search?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())["results"]


def evaluate(api_base: str, token: str, queries: list[dict]) -> dict:
    per_query = []
    recall_hits = 0
    mrr_sum = 0.0
    for q in queries:
        expected = set(q.get("expected_top10") or q.get("expected_top3") or [])
        results = search(api_base, token, q["query"])
        result_doc_ids = [r["doc_id"] for r in results]
        top10 = result_doc_ids[:10]
        # Recall@10: did any expected doc appear in top10?
        hit = any(e in top10 for e in expected)
        if hit:
            recall_hits += 1
        # MRR: 1/rank of first expected hit
        rr = 0.0
        for rank, doc_id in enumerate(top10, start=1):
            if doc_id in expected:
                rr = 1.0 / rank
                break
        mrr_sum += rr
        per_query.append(
            {
                "id": q["id"],
                "query": q["query"][:60],
                "expected": sorted(expected),
                "top3_returned": top10[:3],
                "hit": hit,
                "rr": round(rr, 4),
            }
        )
    n = len(queries)
    return {
        "n": n,
        "recall_at_10": recall_hits / n if n else 0.0,
        "mrr": mrr_sum / n if n else 0.0,
        "per_query": per_query,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["smoke", "full"], default="smoke")
    parser.add_argument("--api", default=os.environ.get("API_BASE", "http://localhost:8000"))
    args = parser.parse_args()

    benchmark = json.loads(BENCH.read_text(encoding="utf-8"))
    limit = 5 if args.mode == "smoke" else len(benchmark)
    selected = benchmark[:limit]

    print(f"Mode: {args.mode}  queries: {len(selected)}  api: {args.api}")
    try:
        token = login(args.api)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: login failed: {exc}", file=sys.stderr)
        return 2

    result = evaluate(args.api, token, selected)
    for row in result["per_query"]:
        flag = "PASS" if row["hit"] else "FAIL"
        print(f"  [{flag}] q{row['id']:>2}  rr={row['rr']:.3f}  {row['query']}")
        if not row["hit"]:
            print(f"         expected: {row['expected']}")
            print(f"         got top3: {row['top3_returned']}")

    print(f"\nRecall@10: {result['recall_at_10']:.3f}  (threshold {RECALL_AT_10_THRESHOLD})")
    print(f"MRR:       {result['mrr']:.3f}  (threshold {MRR_THRESHOLD})")

    if result["recall_at_10"] < RECALL_AT_10_THRESHOLD or result["mrr"] < MRR_THRESHOLD:
        print("\nQuality gate FAILED")
        return 1
    print("\nQuality gate PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
