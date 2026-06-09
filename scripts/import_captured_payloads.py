import argparse
import glob
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from api.main import build_recommendation_response
from scripts.replay_analysis import replay_analysis
from scripts.replay_mod_payloads import load_jsonl
from sts_engine.knowledge_base import load_knowledge_base, normalize_id


DEFAULT_SAMPLE = ROOT / "data" / "mod_payload_replay_sample.jsonl"
DEFAULT_CAPTURE_GLOB = ROOT / "artifacts" / "mod_payloads" / "*.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "captured_eval_candidates.json"
DEFAULT_REPORT_JSON = ROOT / "reports" / "captured_payload_import_report.json"
DEFAULT_REPORT_MD = ROOT / "reports" / "captured_payload_import_report.md"


def display_path(path: str | Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def expand_inputs(patterns: Iterable[str]) -> List[Path]:
    paths: List[Path] = []
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            paths.extend(Path(match) for match in matches)
        else:
            paths.append(Path(pattern))
    existing = []
    missing = []
    for path in paths:
        if path.exists():
            existing.append(path)
        else:
            missing.append(path)
    if missing:
        missing_text = ", ".join(str(path) for path in missing)
        raise SystemExit(f"Input payload file(s) not found: {missing_text}")
    return sorted(set(existing), key=lambda path: str(path).lower())


def default_inputs() -> List[Path]:
    artifact_matches = sorted(DEFAULT_CAPTURE_GLOB.parent.glob(DEFAULT_CAPTURE_GLOB.name))
    if artifact_matches:
        return artifact_matches
    return [DEFAULT_SAMPLE]


def safe_id(value: Any) -> str:
    text = normalize_id(str(value or "unknown"))
    return re.sub(r"[^a-z0-9_]+", "_", text).strip("_") or "unknown"


def normalize_expected_id(value: str, state: Dict[str, Any]) -> str:
    character_class = state.get("character_class", "")
    kb = load_knowledge_base()
    if safe_id(value) in {"skip", "skip_card"}:
        return "skip"
    return kb.resolve_id(value, character_class) or safe_id(value)


def case_id_for(record: Dict[str, Any], file_index: int, record_index: int) -> str:
    state = record.get("state") or {}
    run_id = safe_id(state.get("run_id") or "run")
    screen = safe_id(record.get("screen") or state.get("current_screen") or "screen")
    query_type = safe_id(record.get("query_type") or state.get("query_type") or "query")
    timestamp = safe_id(record.get("timestamp") or record_index)
    return f"captured_{run_id}_{screen}_{query_type}_{timestamp}_{file_index}_{record_index}"


def build_candidate(record: Dict[str, Any], source_file: Path, file_index: int, record_index: int) -> Dict[str, Any] | None:
    if record.get("kind") != "recommendation":
        return None
    raw_state = dict(record.get("state") or {})
    state = dict(raw_state)
    query_type = record.get("query_type") or state.get("query_type")
    options = list(record.get("options") or state.get("options") or [])
    if not query_type:
        return None
    state.update(
        {
            "query_type": query_type,
            "options": options,
            "user_query": record.get("user_query") or "Captured Mod payload import.",
        }
    )
    response = build_recommendation_response(state)
    response_data = response.model_dump()
    scores = response_data.get("option_scores") or []
    analysis = replay_analysis(record, response_data, response_data.get("latency_ms", 0.0))
    if scores:
        expected_top = str(scores[0].get("option_id") or "")
    else:
        captured_top = str((record.get("response_summary") or {}).get("top_recommendation") or "")
        expected_top = normalize_expected_id(captured_top, state) if captured_top else ""
    if not expected_top:
        return None
    candidate_id = case_id_for(record, file_index, record_index)
    eval_state = dict(raw_state)
    eval_state["run_id"] = candidate_id
    eval_state.pop("query_type", None)
    eval_state.pop("options", None)
    eval_state.pop("user_query", None)
    return {
        "id": candidate_id,
        "query_type": query_type,
        "state": eval_state,
        "options": options,
        "expected_top": expected_top,
        "acceptable": [expected_top],
        "label_status": "machine_seeded_needs_human_review",
        "label_source": "mod_payload_replay_top",
        "metadata": {
            "source_file": display_path(source_file),
            "record_index": record_index,
            "timestamp": record.get("timestamp", ""),
            "screen": record.get("screen", ""),
            "scene_type": response_data.get("scene_type", ""),
            "selected_skill": response_data.get("selected_skill", ""),
            "captured_top": (record.get("response_summary") or {}).get("top_recommendation", ""),
            "replay_top": scores[0].get("name", "") if scores else "",
            "score_gap": analysis.get("score_gap", 0),
            "score_spread": analysis.get("score_spread", 0),
            "skip_rank": analysis.get("skip_rank"),
            "quality_flags": analysis.get("quality_flags", []),
            "critic_warnings": response_data.get("critic_warnings", []),
            "latency_ms": response_data.get("latency_ms", 0),
            "top_reasons": analysis.get("top_reasons", []),
            "top_risks": analysis.get("top_risks", []),
        },
    }


def import_payloads(paths: List[Path]) -> Dict[str, Any]:
    cases: List[Dict[str, Any]] = []
    skipped = Counter()
    records_total = 0
    for file_index, path in enumerate(paths, start=1):
        records = load_jsonl(path)
        records_total += len(records)
        for record_index, record in enumerate(records, start=1):
            if record.get("kind") != "recommendation":
                skipped["non_recommendation"] += 1
                continue
            candidate = build_candidate(record, path, file_index, record_index)
            if candidate is None:
                skipped["unimportable_recommendation"] += 1
                continue
            cases.append(candidate)
    return {
        "inputs": [display_path(path) for path in paths],
        "records_total": records_total,
        "cases": cases,
        "skipped": dict(skipped),
    }


def summarize(import_result: Dict[str, Any]) -> Dict[str, Any]:
    cases = import_result["cases"]
    by_query: Dict[str, int] = defaultdict(int)
    by_screen: Dict[str, int] = defaultdict(int)
    flags = Counter()
    review_priority = Counter()
    for case in cases:
        by_query[case["query_type"]] += 1
        metadata = case.get("metadata", {})
        by_screen[metadata.get("screen", "") or "unknown"] += 1
        case_flags = list(metadata.get("quality_flags") or [])
        flags.update(case_flags)
        if case_flags or metadata.get("critic_warnings") or float(metadata.get("score_gap") or 0) < 5:
            review_priority["high"] += 1
        else:
            review_priority["normal"] += 1
    return {
        "inputs": import_result["inputs"],
        "records_total": import_result["records_total"],
        "imported_cases": len(cases),
        "skipped": import_result["skipped"],
        "by_query_type": dict(sorted(by_query.items())),
        "by_screen": dict(sorted(by_screen.items())),
        "quality_flags": dict(sorted(flags.items())),
        "review_priority": dict(sorted(review_priority.items())),
        "sample_case_ids": [case["id"] for case in cases[:8]],
    }


def markdown_report(summary: Dict[str, Any], output_path: Path) -> str:
    lines = [
        "# Captured Payload Import Report",
        "",
        "This report summarizes machine-seeded eval candidates generated from Java Mod JSONL payloads.",
        "",
        "Important: imported cases are marked `machine_seeded_needs_human_review`. They should be reviewed before being merged into `data/public_eval_cases.json`.",
        "",
        f"- Output candidate file: `{display_path(output_path)}`",
        f"- Input files: {', '.join(f'`{path}`' for path in summary['inputs'])}",
        f"- Raw records: {summary['records_total']}",
        f"- Imported eval candidates: {summary['imported_cases']}",
        f"- Skipped records: {sum(summary['skipped'].values())}",
        "",
        "## Coverage",
        "",
        "| Query Type | Candidates |",
        "| --- | ---: |",
    ]
    for query_type, count in summary["by_query_type"].items():
        lines.append(f"| {query_type} | {count} |")
    lines.extend(["", "## Screens", "", "| Screen | Candidates |", "| --- | ---: |"])
    for screen, count in summary["by_screen"].items():
        lines.append(f"| {screen} | {count} |")
    lines.extend(["", "## Quality Flags", "", "| Flag | Count |", "| --- | ---: |"])
    if summary["quality_flags"]:
        for flag, count in summary["quality_flags"].items():
            lines.append(f"| {flag} | {count} |")
    else:
        lines.append("| none | 0 |")
    lines.extend(["", "## Review Priority", "", "| Priority | Count |", "| --- | ---: |"])
    for priority, count in summary["review_priority"].items():
        lines.append(f"| {priority} | {count} |")
    lines.extend(
        [
            "",
            "## Next Review Steps",
            "",
            "1. Open the generated candidate JSON.",
            "2. For each case, inspect `metadata.replay_top`, `score_gap`, `quality_flags`, and `top_reasons`.",
            "3. Change `label_status` to `human_labeled` after review.",
            "4. Adjust `expected_top` and `acceptable` if the machine-seeded recommendation is not the human label.",
            "5. Merge reviewed cases into the fixed eval set or keep them as a separate real-payload eval file.",
            "",
        ]
    )
    if summary["sample_case_ids"]:
        lines.extend(["## Sample Case IDs", ""])
        lines.extend(f"- `{case_id}`" for case_id in summary["sample_case_ids"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert captured Java Mod JSONL payloads into machine-seeded eval candidates.")
    parser.add_argument("paths", nargs="*", help="Captured JSONL files or glob patterns. Defaults to artifacts/mod_payloads/*.jsonl, then sample replay.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--report-json", default=str(DEFAULT_REPORT_JSON))
    parser.add_argument("--report-md", default=str(DEFAULT_REPORT_MD))
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()

    paths = expand_inputs(args.paths) if args.paths else default_inputs()
    import_result = import_payloads(paths)
    summary = summarize(import_result)
    output_path = Path(args.output)
    printed = summary if args.summary_only else {"summary": summary, "cases": import_result["cases"]}
    print(json.dumps(printed, ensure_ascii=False, indent=2))
    if not args.no_write:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        report_json = Path(args.report_json)
        report_md = Path(args.report_md)
        report_json.parent.mkdir(parents=True, exist_ok=True)
        report_md.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(import_result["cases"], ensure_ascii=False, indent=2), encoding="utf-8")
        report_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        report_md.write_text(markdown_report(summary, output_path), encoding="utf-8")


if __name__ == "__main__":
    main()
