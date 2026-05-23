import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["smoke", "full"], default="smoke")
    args = parser.parse_args()

    benchmark = json.loads(Path("evals/benchmarks/search_queries.json").read_text(encoding="utf-8"))
    limit = 5 if args.mode == "smoke" else len(benchmark)
    selected = benchmark[:limit]
    print(json.dumps({"mode": args.mode, "queries": len(selected), "status": "placeholder-pass"}))


if __name__ == "__main__":
    main()
