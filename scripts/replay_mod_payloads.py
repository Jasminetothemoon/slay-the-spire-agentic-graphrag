import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.main import build_recommendation_response
from scripts.replay_analysis import replay_analysis


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
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


def replay_record(record: Dict[str, Any]) -> Dict[str, Any]:
    if record.get("kind") != "recommendation":
        return {
            "kind": record.get("kind", "unknown"),
            "status": "skipped",
            "reason": "Only recommendation payloads are replayed.",
        }

    state = dict(record.get("state") or {})
    query_type = record.get("query_type") or state.get("query_type")
    options = list(record.get("options") or state.get("options") or [])
    state.update(
        {
            "query_type": query_type,
            "options": options,
            "user_query": record.get("user_query") or "Replay captured Mod payload.",
        }
    )
    response = build_recommendation_response(state)
    scores = response.option_scores
    response_data = response.model_dump()
    analysis = replay_analysis(record, response_data, response.latency_ms)
    return {
        "kind": "recommendation",
        "status": "passed" if scores else "failed",
        "screen": record.get("screen", ""),
        "query_type": query_type,
        "options_count": len(options),
        "scene_type": response.scene_type,
        "recommendation": response.recommendation,
        "top_option": scores[0].get("name") if scores else "",
        "scores": len(scores),
        "latency_ms": response.latency_ms,
        "analysis": analysis,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay JSONL payloads captured by the Java Mod bridge.")
    parser.add_argument("path", help="Path to a captured Mod JSONL file.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    path = Path(args.path)
    records = load_jsonl(path)
    reports = [replay_record(record) for record in records]
    failures = [item for item in reports if item.get("status") == "failed"]
    summary = {
        "file": str(path),
        "records": len(records),
        "replayed": sum(1 for item in reports if item.get("kind") == "recommendation"),
        "failures": len(failures),
        "reports": reports,
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Replayed {summary['replayed']} recommendation payload(s) from {path}.")
        print(f"Failures: {summary['failures']}")
        for item in reports:
            if item.get("kind") != "recommendation":
                continue
            print(
                f"- {item['status']} {item.get('screen', '')} {item.get('query_type', '')}: "
                f"{item.get('top_option', '') or item.get('recommendation', '')} ({item.get('scores', 0)} scores)"
            )
            analysis = item.get("analysis", {})
            if analysis:
                flags = ", ".join(analysis.get("quality_flags", [])) or "none"
                print(
                    f"  target={analysis.get('preferred_archetype') or 'auto'} "
                    f"gap={analysis.get('score_gap')} skip_rank={analysis.get('skip_rank')} flags={flags}"
                )
                for option in analysis.get("option_summaries", [])[:3]:
                    print(
                        f"  #{option.get('option_id')} score={option.get('score')} "
                        f"strategy={option.get('strategy_signal')} risks={len(option.get('risks', []))}"
                    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
