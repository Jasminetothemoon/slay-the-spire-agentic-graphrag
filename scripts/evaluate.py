import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_EVAL_PATH = ROOT / "data" / "eval_cases.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate recommendation quality on fixed scenarios.")
    parser.add_argument("--eval", default=str(DEFAULT_EVAL_PATH), help="Path to evaluation cases JSON.")
    parser.add_argument("--data", default=None, help="Optional knowledge-base dataset path.")
    args = parser.parse_args()

    if args.data:
        os.environ["STS_KB_PATH"] = args.data

    from sts_engine.agent import build_graph

    with open(args.eval, "r", encoding="utf-8") as f:
        cases = json.load(f)

    engine = build_graph()
    top1 = 0
    top3 = 0
    latencies = []
    failures = []
    for case in cases:
        state = dict(case["state"])
        state["query_type"] = case["query_type"]
        state["options"] = case["options"]
        started = time.perf_counter()
        result = engine.invoke(state)
        elapsed = (time.perf_counter() - started) * 1000
        latencies.append(elapsed)
        ranked = [item["option_id"] for item in result.get("option_scores", [])]
        expected = case["expected_top"]
        acceptable = set(case.get("acceptable", [expected]))
        if ranked and ranked[0] in acceptable:
            top1 += 1
        elif ranked and ranked[0] not in acceptable:
            failures.append((case["id"], ranked[:3], expected))
        if acceptable.intersection(ranked[:3]):
            top3 += 1

    total = len(cases)
    report = {
        "cases": total,
        "top1_accuracy": round(top1 / total, 3),
        "top3_accuracy": round(top3 / total, 3),
        "mean_latency_ms": round(statistics.mean(latencies), 2),
        "p95_latency_ms": round(sorted(latencies)[int((total - 1) * 0.95)], 2),
        "failures": failures,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
