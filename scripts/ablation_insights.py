import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from scripts.decision_harness import DEFAULT_DATA, DEFAULT_EVAL, invoke_case, load_json, run_ablation, summarize_eval
from sts_engine.knowledge_base import load_knowledge_base, normalize_id


DEFAULT_JSON_OUTPUT = ROOT / "reports" / "ablation_insights.json"
DEFAULT_MD_OUTPUT = ROOT / "reports" / "ablation_insights.md"


def display_path(path: str | Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def normalize_option_id(option: str, kb: Any, character_class: str | None) -> str:
    if normalize_id(str(option)) in {"skip", "skip_card"}:
        return "skip"
    return kb.resolve_id(str(option), character_class) or normalize_id(str(option))


def baseline_case_report(case: Dict[str, Any], kb: Any, baseline: str) -> Dict[str, Any]:
    options = list(case.get("options", []))
    character_class = case.get("state", {}).get("character_class", "")
    if baseline == "input_order":
        ranked = [normalize_option_id(option, kb, character_class) for option in options]
    elif baseline == "base_value":
        entities = []
        for index, option in enumerate(options):
            entity_id = normalize_option_id(option, kb, character_class)
            entity = kb.get(option, character_class) or {"id": entity_id, "name": option, "base_value": 35}
            entities.append(
                {
                    "index": index,
                    "option_id": entity_id,
                    "base_value": float(entity.get("base_value", 35)),
                    "name": str(entity.get("name", option)),
                }
            )
        ranked = [
            item["option_id"]
            for item in sorted(entities, key=lambda item: (-item["base_value"], item["name"], item["index"]))
        ]
    else:
        raise ValueError(f"Unsupported baseline: {baseline}")

    expected = case["expected_top"]
    acceptable = set(case.get("acceptable", [expected]))
    return {
        "id": case["id"],
        "query_type": case["query_type"],
        "ranked_top3": ranked[:3],
        "expected": expected,
        "top1_hit": bool(ranked and ranked[0] in acceptable),
        "top3_hit": bool(acceptable.intersection(ranked[:3])),
        "latency_ms": 0.0,
        "selected_skill": baseline,
        "agent_trace_count": 0,
        "critic_warnings": [],
        "decision_valid": bool(ranked),
        "no_recommendation": not bool(ranked),
    }


def run_baselines(cases: List[Dict[str, Any]], kb: Any) -> Dict[str, Any]:
    baselines = {}
    for name in ("input_order", "base_value"):
        reports = [baseline_case_report(case, kb, name) for case in cases]
        baselines[name] = {"summary": summarize_eval(reports), "cases": reports}
    return baselines


def run_full_eval(engine: Any, cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    reports = [invoke_case(engine, case) for case in cases]
    return {"summary": summarize_eval(reports), "cases": reports}


def delta(value: float, reference: float) -> float:
    return round(float(value) - float(reference), 3)


def build_report(data_path: Path, eval_path: Path) -> Dict[str, Any]:
    os.environ["STS_KB_PATH"] = str(data_path)
    load_knowledge_base.cache_clear()
    kb = load_knowledge_base(str(data_path))
    from sts_engine.agent import build_graph

    engine = build_graph()
    cases = load_json(eval_path)
    baselines = run_baselines(cases, kb)
    full_eval = run_full_eval(engine, cases)
    ablations = run_ablation(engine, eval_path)
    full_summary = full_eval["summary"]
    comparisons = {}
    for name, item in baselines.items():
        summary = item["summary"]
        comparisons[name] = {
            "top1_delta_vs_full": delta(summary["top1_accuracy"], full_summary["top1_accuracy"]),
            "top3_delta_vs_full": delta(summary["top3_accuracy"], full_summary["top3_accuracy"]),
        }
    for name, summary in ablations.items():
        comparisons[name] = {
            "top1_delta_vs_full": delta(summary["top1_accuracy"], full_summary["top1_accuracy"]),
            "top3_delta_vs_full": delta(summary["top3_accuracy"], full_summary["top3_accuracy"]),
            "p95_delta_ms_vs_full": delta(summary["p95_latency_ms"], full_summary["p95_latency_ms"]),
        }
    return {
        "eval_file": display_path(eval_path),
        "cases": len(cases),
        "baselines": baselines,
        "full": full_eval,
        "ablations": ablations,
        "comparisons": comparisons,
    }


def table_row(name: str, summary: Dict[str, Any], extra: str = "") -> str:
    return (
        f"| {name} | {summary['cases']} | {summary['top1_accuracy']} | {summary['top3_accuracy']} | "
        f"{summary['p95_latency_ms']} | {summary['no_recommendation_rate']} | {summary['critic_warning_rate']} | {extra} |"
    )


def markdown_report(report: Dict[str, Any]) -> str:
    full = report["full"]["summary"]
    lines = [
        "# Ablation and Baseline Insights",
        "",
        "This report is generated from the fixed eval set. It compares simple deterministic baselines, the full Multi-Agent Decision Harness, and module-level ablations.",
        "",
        f"- Eval file: `{display_path(report['eval_file'])}`",
        f"- Cases: {report['cases']}",
        f"- Full system Top-1 / Top-3: {full['top1_accuracy']} / {full['top3_accuracy']}",
        f"- Full system P95 latency: {full['p95_latency_ms']} ms",
        "",
        "## Baseline Comparison",
        "",
        "| Variant | Cases | Top-1 | Top-3 | P95 ms | No Recommendation | Critic Warning | Delta vs Full |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for name, item in report["baselines"].items():
        cmp = report["comparisons"][name]
        lines.append(
            table_row(
                name,
                item["summary"],
                f"Top-1 {cmp['top1_delta_vs_full']}, Top-3 {cmp['top3_delta_vs_full']}",
            )
        )
    lines.append(table_row("full_multi_agent", full, "reference"))
    lines.extend(
        [
            "",
            "## Module Ablation",
            "",
            "| Variant | Cases | Top-1 | Top-3 | P95 ms | No Recommendation | Critic Warning | Delta vs Full |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for name, summary in report["ablations"].items():
        cmp = report["comparisons"][name]
        lines.append(
            table_row(
                name,
                summary,
                f"Top-1 {cmp['top1_delta_vs_full']}, Top-3 {cmp['top3_delta_vs_full']}, P95 {cmp['p95_delta_ms_vs_full']} ms",
            )
        )

    lines.extend(
        [
            "",
            "## Full System By Query Type",
            "",
            "| Query Type | Cases | Top-1 | Top-3 |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for query_type, values in full["by_type"].items():
        lines.append(f"| {query_type} | {values['cases']} | {values['top1_accuracy']} | {values['top3_accuracy']} |")

    lines.extend(
        [
            "",
            "## Interview Takeaways",
            "",
            "- `input_order` measures how often the eval fixture order accidentally puts the best option first.",
            "- `base_value` measures a naive tier/value strategy that ignores deck state, target archetype, graph evidence, risk, price, and legality.",
            "- `full_multi_agent` is the production path: StateAgent -> SceneRouterAgent -> RetrievalAgent -> RiskAgent -> SkillScoringAgent -> CriticAgent -> ExplainerAgent.",
            "- Module ablations are most useful after adding more real, noisy payloads; on a curated eval set they mainly verify that switches stay stable and measurable.",
            "- The key engineering value is not a single score, but a repeatable harness that can compare recommendation policies as the dataset grows.",
            "",
        ]
    )
    return "\n".join(lines)


def compact_summary(report: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "cases": report["cases"],
        "full": report["full"]["summary"],
        "baselines": {name: item["summary"] for name, item in report["baselines"].items()},
        "ablations": report["ablations"],
        "comparisons": report["comparisons"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate interview-ready baseline and ablation insights.")
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--eval", default=str(DEFAULT_EVAL))
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--md-output", default=str(DEFAULT_MD_OUTPUT))
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()

    report = build_report(Path(args.data), Path(args.eval))
    printed = compact_summary(report) if args.summary_only else report
    print(json.dumps(printed, ensure_ascii=False, indent=2))
    if not args.no_write:
        json_output = Path(args.json_output)
        md_output = Path(args.md_output)
        json_output.parent.mkdir(parents=True, exist_ok=True)
        md_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        md_output.write_text(markdown_report(report), encoding="utf-8")


if __name__ == "__main__":
    main()
