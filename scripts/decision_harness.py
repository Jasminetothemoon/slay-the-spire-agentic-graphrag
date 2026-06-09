import argparse
import json
import os
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_DATA = ROOT / "data" / "public_full_data.json"
DEFAULT_EVAL = ROOT / "data" / "public_eval_cases.json"
DEFAULT_REPLAY = ROOT / "data" / "mod_payload_replay_sample.jsonl"
DEFAULT_JSON_OUTPUT = ROOT / "reports" / "decision_harness_report.json"
DEFAULT_MD_OUTPUT = ROOT / "reports" / "decision_harness_report.md"

from scripts.replay_analysis import replay_analysis


ABLATIONS = {
    "full": {},
    "no_graph": {"_ablation_disable_graph": True},
    "no_strategy": {"_ablation_disable_strategy": True},
    "no_risk": {"_ablation_disable_risk": True},
    "no_critic": {"_ablation_disable_critic": True},
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                records.append(json.loads(text))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_no}: invalid JSONL record: {exc}") from exc
    return records


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int((len(ordered) - 1) * pct)
    return round(ordered[index], 2)


def invoke_case(engine: Any, case: Dict[str, Any], flags: Dict[str, Any] | None = None) -> Dict[str, Any]:
    state = dict(case["state"])
    state["query_type"] = case["query_type"]
    state["options"] = case["options"]
    if flags:
        state.update(flags)
    started = time.perf_counter()
    result = engine.invoke(state)
    elapsed = (time.perf_counter() - started) * 1000
    ranked = [item["option_id"] for item in result.get("option_scores", [])]
    expected = case["expected_top"]
    acceptable = set(case.get("acceptable", [expected]))
    return {
        "id": case["id"],
        "query_type": case["query_type"],
        "ranked_top3": ranked[:3],
        "expected": expected,
        "top1_hit": bool(ranked and ranked[0] in acceptable),
        "top3_hit": bool(acceptable.intersection(ranked[:3])),
        "latency_ms": round(elapsed, 2),
        "selected_skill": result.get("selected_skill", ""),
        "agent_trace_count": len(result.get("agent_trace", [])),
        "critic_warnings": result.get("critic_warnings", []),
        "decision_valid": result.get("decision_valid", False),
        "no_recommendation": not bool(ranked),
    }


def summarize_eval(case_reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(case_reports)
    latencies = [item["latency_ms"] for item in case_reports]
    by_type: Dict[str, Dict[str, int]] = defaultdict(lambda: {"cases": 0, "top1": 0, "top3": 0})
    for item in case_reports:
        bucket = by_type[item["query_type"]]
        bucket["cases"] += 1
        bucket["top1"] += int(item["top1_hit"])
        bucket["top3"] += int(item["top3_hit"])
    return {
        "cases": total,
        "top1_accuracy": round(sum(1 for item in case_reports if item["top1_hit"]) / total, 3) if total else 0,
        "top3_accuracy": round(sum(1 for item in case_reports if item["top3_hit"]) / total, 3) if total else 0,
        "mean_latency_ms": round(statistics.mean(latencies), 2) if latencies else 0,
        "p50_latency_ms": percentile(latencies, 0.50),
        "p95_latency_ms": percentile(latencies, 0.95),
        "p99_latency_ms": percentile(latencies, 0.99),
        "no_recommendation_rate": round(sum(1 for item in case_reports if item["no_recommendation"]) / total, 3) if total else 0,
        "critic_warning_rate": round(sum(1 for item in case_reports if item["critic_warnings"]) / total, 3) if total else 0,
        "by_type": {
            query_type: {
                "cases": values["cases"],
                "top1_accuracy": round(values["top1"] / values["cases"], 3),
                "top3_accuracy": round(values["top3"] / values["cases"], 3),
            }
            for query_type, values in sorted(by_type.items())
        },
        "failures": [
            {"id": item["id"], "ranked_top3": item["ranked_top3"], "expected": item["expected"]}
            for item in case_reports
            if not item["top1_hit"]
        ],
    }


def run_eval(engine: Any, eval_path: Path) -> Dict[str, Any]:
    cases = load_json(eval_path)
    reports = [invoke_case(engine, case) for case in cases]
    return {"summary": summarize_eval(reports), "cases": reports}


def run_ablation(engine: Any, eval_path: Path) -> Dict[str, Any]:
    cases = load_json(eval_path)
    results = {}
    for name, flags in ABLATIONS.items():
        reports = [invoke_case(engine, case, flags=flags) for case in cases]
        results[name] = summarize_eval(reports)
    return results


def run_latency(engine: Any, eval_path: Path) -> Dict[str, Any]:
    reports = [invoke_case(engine, case) for case in load_json(eval_path)]
    latencies = [item["latency_ms"] for item in reports]
    return {
        "cases": len(reports),
        "p50_latency_ms": percentile(latencies, 0.50),
        "p95_latency_ms": percentile(latencies, 0.95),
        "p99_latency_ms": percentile(latencies, 0.99),
        "mean_latency_ms": round(statistics.mean(latencies), 2) if latencies else 0,
    }


def replay_record(engine: Any, record: Dict[str, Any]) -> Dict[str, Any]:
    if record.get("kind") != "recommendation":
        return {"status": "skipped", "kind": record.get("kind", "unknown")}
    state = dict(record.get("state") or {})
    state["query_type"] = record.get("query_type") or state.get("query_type")
    state["options"] = list(record.get("options") or state.get("options") or [])
    started = time.perf_counter()
    result = engine.invoke(state)
    elapsed = (time.perf_counter() - started) * 1000
    scores = result.get("option_scores", [])
    analysis = replay_analysis(record, result, elapsed)
    return {
        "status": "passed" if scores else "failed",
        "screen": record.get("screen", ""),
        "query_type": state.get("query_type", ""),
        "scene_type": result.get("scene_type", ""),
        "recommendation": result.get("recommendation", ""),
        "top_option": scores[0].get("name") if scores else "",
        "scores": len(scores),
        "latency_ms": round(elapsed, 2),
        "selected_skill": result.get("selected_skill", ""),
        "critic_warnings": result.get("critic_warnings", []),
        "analysis": analysis,
    }


def run_replay(engine: Any, replay_path: Path) -> Dict[str, Any]:
    records = load_jsonl(replay_path)
    reports = [replay_record(engine, record) for record in records]
    return {
        "file": str(replay_path),
        "records": len(records),
        "replayed": sum(1 for item in reports if item.get("status") != "skipped"),
        "failures": sum(1 for item in reports if item.get("status") == "failed"),
        "reports": reports,
    }


def markdown_report(report: Dict[str, Any]) -> str:
    lines = ["# Decision Harness Report", ""]
    if "eval" in report:
        summary = report["eval"]["summary"]
        lines.extend(
            [
                "## Eval Harness",
                "",
                f"- Cases: {summary['cases']}",
                f"- Top-1 accuracy: {summary['top1_accuracy']}",
                f"- Top-3 accuracy: {summary['top3_accuracy']}",
                f"- P95 latency: {summary['p95_latency_ms']} ms",
                f"- No recommendation rate: {summary['no_recommendation_rate']}",
                f"- Critic warning rate: {summary['critic_warning_rate']}",
                "",
            ]
        )
    if "ablation" in report:
        lines.extend(["## Ablation Harness", "", "| Variant | Top-1 | Top-3 | P95 ms | No Recommendation |", "|---|---:|---:|---:|---:|"])
        for name, summary in report["ablation"].items():
            lines.append(
                f"| {name} | {summary['top1_accuracy']} | {summary['top3_accuracy']} | {summary['p95_latency_ms']} | {summary['no_recommendation_rate']} |"
            )
        lines.append("")
    if "latency" in report:
        latency = report["latency"]
        lines.extend(
            [
                "## Latency Harness",
                "",
                f"- Mean: {latency['mean_latency_ms']} ms",
                f"- P50: {latency['p50_latency_ms']} ms",
                f"- P95: {latency['p95_latency_ms']} ms",
                f"- P99: {latency['p99_latency_ms']} ms",
                "",
            ]
        )
    if "replay" in report:
        replay = report["replay"]
        lines.extend(
            [
                "## Replay Harness",
                "",
                f"- File: `{replay['file']}`",
                f"- Records: {replay['records']}",
                f"- Replayed: {replay['replayed']}",
                f"- Failures: {replay['failures']}",
                "",
            ]
        )
        for item in replay.get("reports", [])[:10]:
            if item.get("status") == "skipped":
                continue
            analysis = item.get("analysis", {})
            flags = ", ".join(analysis.get("quality_flags", [])) or "none"
            lines.append(
                f"- {item.get('screen', '')} `{item.get('query_type', '')}`: "
                f"{item.get('top_option', '') or item.get('recommendation', '')}; "
                f"target={analysis.get('preferred_archetype') or 'auto'}, "
                f"gap={analysis.get('score_gap')}, skip_rank={analysis.get('skip_rank')}, flags={flags}"
            )
        lines.append("")
    return "\n".join(lines)


def summary_report(report: Dict[str, Any]) -> Dict[str, Any]:
    compact: Dict[str, Any] = {}
    if "eval" in report:
        compact["eval"] = report["eval"]["summary"]
    if "ablation" in report:
        compact["ablation"] = {
            name: {
                "top1_accuracy": summary["top1_accuracy"],
                "top3_accuracy": summary["top3_accuracy"],
                "p95_latency_ms": summary["p95_latency_ms"],
                "no_recommendation_rate": summary["no_recommendation_rate"],
            }
            for name, summary in report["ablation"].items()
        }
    if "latency" in report:
        compact["latency"] = report["latency"]
    if "replay" in report:
        compact["replay"] = {
            "file": report["replay"]["file"],
            "records": report["replay"]["records"],
            "replayed": report["replay"]["replayed"],
            "failures": report["replay"]["failures"],
        }
    return compact


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified decision harness for eval, replay, ablation, and latency checks.")
    parser.add_argument("--mode", choices=["eval", "replay", "ablation", "latency", "all"], default="all")
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--eval", default=str(DEFAULT_EVAL))
    parser.add_argument("--replay", default=str(DEFAULT_REPLAY))
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--md-output", default=str(DEFAULT_MD_OUTPUT))
    parser.add_argument("--no-write", action="store_true", help="Print results without writing report files.")
    parser.add_argument("--summary-only", action="store_true", help="Print compact summaries instead of per-case details.")
    args = parser.parse_args()

    os.environ["STS_KB_PATH"] = args.data
    from sts_engine.agent import build_graph

    engine = build_graph()
    report: Dict[str, Any] = {}
    if args.mode in {"eval", "all"}:
        report["eval"] = run_eval(engine, Path(args.eval))
    if args.mode in {"ablation", "all"}:
        report["ablation"] = run_ablation(engine, Path(args.eval))
    if args.mode in {"latency", "all"}:
        report["latency"] = run_latency(engine, Path(args.eval))
    if args.mode in {"replay", "all"}:
        report["replay"] = run_replay(engine, Path(args.replay))

    printed_report = summary_report(report) if args.summary_only else report
    print(json.dumps(printed_report, ensure_ascii=False, indent=2))
    if not args.no_write:
        json_output = Path(args.json_output)
        md_output = Path(args.md_output)
        json_output.parent.mkdir(parents=True, exist_ok=True)
        md_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        md_output.write_text(markdown_report(report), encoding="utf-8")

    failures = []
    if report.get("eval", {}).get("summary", {}).get("failures"):
        failures.append("eval failures")
    if report.get("replay", {}).get("failures", 0):
        failures.append("replay failures")
    if failures:
        raise SystemExit("; ".join(failures))


if __name__ == "__main__":
    main()
