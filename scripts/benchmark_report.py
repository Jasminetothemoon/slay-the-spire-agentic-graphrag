import argparse
import json
import os
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_DATA = ROOT / "data" / "public_full_data.json"
DEFAULT_EVAL = ROOT / "data" / "public_eval_cases.json"
DEFAULT_LOCALIZATION = ROOT / "data" / "localization_zhs.json"
DEFAULT_OUTPUT = ROOT / "reports" / "benchmark.md"

COLLECTIONS = ("classes", "mechanics", "cards", "relics", "potions", "enemies", "shop_actions", "path_nodes")
AGENT_NODES = ("validate_state", "retrieve_context", "assess_risk", "score_options", "explain_decision")


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def graph_stats(data: Dict[str, Any]) -> Dict[str, Any]:
    relationship_counts: Counter[str] = Counter()
    missing_provenance = 0
    total_relationships = 0
    for collection in COLLECTIONS:
        for entity in data.get(collection, []):
            for relationship in entity.get("relationships", []):
                total_relationships += 1
                relationship_counts[relationship.get("type", "missing")] += 1
                if not relationship.get("source") or not relationship.get("source_url") or relationship.get("confidence") is None:
                    missing_provenance += 1
    return {
        "node_counts": {collection: len(data.get(collection, [])) for collection in COLLECTIONS},
        "relationship_counts": dict(sorted(relationship_counts.items())),
        "total_relationships": total_relationships,
        "relationships_missing_provenance": missing_provenance,
    }


def evaluate(data_path: Path, eval_path: Path) -> Dict[str, Any]:
    os.environ["STS_KB_PATH"] = str(data_path)

    from sts_engine.agent import build_graph

    cases = load_json(eval_path)
    engine = build_graph()
    top1 = 0
    top3 = 0
    latencies: List[float] = []
    failures: List[Dict[str, Any]] = []
    by_type: Dict[str, Dict[str, int]] = {}

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
        query_type = case["query_type"]
        by_type.setdefault(query_type, {"cases": 0, "top1": 0, "top3": 0})
        by_type[query_type]["cases"] += 1

        top1_hit = bool(ranked and ranked[0] in acceptable)
        top3_hit = bool(acceptable.intersection(ranked[:3]))
        top1 += int(top1_hit)
        top3 += int(top3_hit)
        by_type[query_type]["top1"] += int(top1_hit)
        by_type[query_type]["top3"] += int(top3_hit)
        if ranked and not top1_hit:
            failures.append({"id": case["id"], "ranked_top3": ranked[:3], "expected": expected})

    total = len(cases)
    sorted_latencies = sorted(latencies)
    p95_index = int((total - 1) * 0.95) if total else 0
    return {
        "cases": total,
        "top1_accuracy": round(top1 / total, 3) if total else 0,
        "top3_accuracy": round(top3 / total, 3) if total else 0,
        "mean_latency_ms": round(statistics.mean(latencies), 2) if latencies else 0,
        "p95_latency_ms": round(sorted_latencies[p95_index], 2) if sorted_latencies else 0,
        "failures": failures,
        "by_type": {
            query_type: {
                "cases": values["cases"],
                "top1_accuracy": round(values["top1"] / values["cases"], 3),
                "top3_accuracy": round(values["top3"] / values["cases"], 3),
            }
            for query_type, values in sorted(by_type.items())
        },
    }


def localization_stats(data: Dict[str, Any], localization: Dict[str, Any]) -> Dict[str, Any]:
    entities = localization.get("entities", {})
    localizable_ids = {
        entity["id"]
        for collection in ("cards", "relics", "potions", "enemies")
        for entity in data.get(collection, [])
    }
    localized_ids = localizable_ids.intersection(entities)
    return {
        "localized_entities": len(localized_ids),
        "localizable_entities": len(localizable_ids),
        "coverage_pct": round(len(localized_ids) / len(localizable_ids) * 100, 2) if localizable_ids else 0,
        "source": localization.get("metadata", {}).get("source", "unknown"),
    }


def markdown_table(headers: List[str], rows: List[List[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def build_markdown(data: Dict[str, Any], graph: Dict[str, Any], eval_report: Dict[str, Any], loc: Dict[str, Any]) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    node_rows = [[name, graph["node_counts"].get(name, 0)] for name in COLLECTIONS]
    relationship_rows = [[name, count] for name, count in graph["relationship_counts"].items()]
    type_rows = [
        [query_type, values["cases"], values["top1_accuracy"], values["top3_accuracy"]]
        for query_type, values in eval_report["by_type"].items()
    ]
    failure_rows = eval_report["failures"] or []
    failure_section = "No failures in the current evaluation set."
    if failure_rows:
        failure_section = markdown_table(
            ["Case", "Expected", "Ranked Top-3"],
            [[item["id"], item["expected"], ", ".join(item["ranked_top3"])] for item in failure_rows],
        )

    return f"""# Benchmark Report

Generated: {generated_at}

## Executive Summary

- Evaluation cases: **{eval_report["cases"]}**
- Top-1 accuracy: **{eval_report["top1_accuracy"]}**
- Top-3 accuracy: **{eval_report["top3_accuracy"]}**
- Mean latency: **{eval_report["mean_latency_ms"]} ms**
- P95 latency: **{eval_report["p95_latency_ms"]} ms**
- Graph entities: **{sum(graph["node_counts"].values())}**
- Graph relationships: **{graph["total_relationships"]}**
- Chinese localization coverage: **{loc["localized_entities"]}/{loc["localizable_entities"]} ({loc["coverage_pct"]}%)**

## Agentic Workflow

The recommendation pipeline is a deterministic LangGraph workflow, not a direct LLM-only answer:

{markdown_table(["Step", "Responsibility"], [
    ["validate_state", "Check run id, class, query type, and available decision options."],
    ["retrieve_context", "Retrieve graph evidence and shared mechanics for the current state."],
    ["assess_risk", "Detect deck-shape and run-state risks such as missing AoE or low HP."],
    ["score_options", "Score legal options with graph evidence, curated strategy rules, and risk coverage."],
    ["explain_decision", "Return a structured recommendation, latency, confidence, reasons, and risks."],
])}

## Evaluation Metrics

{markdown_table(["Query Type", "Cases", "Top-1", "Top-3"], type_rows)}

## Data Scale

{markdown_table(["Collection", "Count"], node_rows)}

## Graph Scale

- Relationships with missing provenance: **{graph["relationships_missing_provenance"]}**

{markdown_table(["Relationship", "Count"], relationship_rows)}

## Localization

- Source: **{loc["source"]}**
- Localized entity names are presentation-layer fields; internal recommendation logic continues to use stable English ids.
- Chinese display is covered by regression checks in `scripts/check_localization.py`.

## Failure Analysis

{failure_section}

## Reproduce

```powershell
.\\.venv\\Scripts\\python.exe scripts\\benchmark_report.py --data data\\public_full_data.json --eval data\\public_eval_cases.json --output reports\\benchmark.md
```
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a resume-ready benchmark report for the Agentic GraphRAG system.")
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--eval", default=str(DEFAULT_EVAL))
    parser.add_argument("--localization", default=str(DEFAULT_LOCALIZATION))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary in addition to writing Markdown.")
    args = parser.parse_args()

    data_path = Path(args.data)
    eval_path = Path(args.eval)
    localization_path = Path(args.localization)
    data = load_json(data_path)
    localization = load_json(localization_path)
    graph = graph_stats(data)
    eval_report = evaluate(data_path, eval_path)
    loc = localization_stats(data, localization)

    markdown = build_markdown(data, graph, eval_report, loc)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")

    summary = {
        "output": str(output),
        "evaluation": eval_report,
        "graph": {
            "entities": sum(graph["node_counts"].values()),
            "relationships": graph["total_relationships"],
            "relationships_missing_provenance": graph["relationships_missing_provenance"],
        },
        "localization": loc,
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Benchmark report written to {output}")


if __name__ == "__main__":
    main()
