import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from scripts.decision_harness import DEFAULT_DATA, DEFAULT_EVAL, invoke_case, load_json
from sts_engine.knowledge_base import load_knowledge_base


DEFAULT_JSON_OUTPUT = ROOT / "reports" / "agent_trace_audit.json"
DEFAULT_MD_OUTPUT = ROOT / "reports" / "agent_trace_audit.md"
REQUIRED_AGENTS = [
    "StateAgent",
    "SceneRouterAgent",
    "RetrievalAgent",
    "RiskAgent",
    "SkillScoringAgent",
    "CriticAgent",
    "ExplainerAgent",
]


def display_path(path: str | Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def pick_cases(cases: List[Dict[str, Any]], max_cases: int) -> List[Dict[str, Any]]:
    selected = []
    seen_query_types = set()
    preferred_order = ["card_pick", "shop", "relic_pick", "combat", "pathing", "rest_site", "smith"]
    for query_type in preferred_order:
        for case in cases:
            if case.get("query_type") == query_type and query_type not in seen_query_types:
                selected.append(case)
                seen_query_types.add(query_type)
                break
            if len(selected) >= max_cases:
                return selected
    if len(selected) < max_cases:
        selected_ids = {case["id"] for case in selected}
        for case in cases:
            if case["id"] not in selected_ids:
                selected.append(case)
            if len(selected) >= max_cases:
                break
    return selected[:max_cases]


def invoke_detailed_case(engine: Any, case: Dict[str, Any]) -> Dict[str, Any]:
    state = dict(case["state"])
    state["query_type"] = case["query_type"]
    state["options"] = case["options"]
    result = engine.invoke(state)
    scores = result.get("option_scores", [])
    trace = result.get("agent_trace", [])
    agents = [item.get("agent", "") for item in trace]
    missing_agents = [agent for agent in REQUIRED_AGENTS if agent not in agents]
    top = scores[0] if scores else {}
    runner_up = scores[1] if len(scores) > 1 else {}
    return {
        "id": case["id"],
        "query_type": case["query_type"],
        "scene_type": result.get("scene_type", ""),
        "selected_skill": result.get("selected_skill", ""),
        "decision_valid": result.get("decision_valid", False),
        "critic_warnings": result.get("critic_warnings", []),
        "latency_ms": result.get("latency_ms", 0),
        "expected_top": case.get("expected_top", ""),
        "ranked_top3": [item.get("option_id", "") for item in scores[:3]],
        "top": {
            "option_id": top.get("option_id", ""),
            "name": top.get("name", ""),
            "score": top.get("score", 0),
            "grade": top.get("grade") or top.get("display_badge", ""),
            "confidence": top.get("confidence", 0),
            "reasons": top.get("reasons", [])[:4],
            "risks": top.get("risks", [])[:3],
            "evidence_count": len(top.get("evidence", [])),
        },
        "runner_up": {
            "option_id": runner_up.get("option_id", ""),
            "name": runner_up.get("name", ""),
            "score": runner_up.get("score", 0),
            "why_not": runner_up.get("why_not", ""),
        },
        "agent_trace": trace,
        "missing_agents": missing_agents,
    }


def build_report(data_path: Path, eval_path: Path, max_cases: int) -> Dict[str, Any]:
    os.environ["STS_KB_PATH"] = str(data_path)
    load_knowledge_base.cache_clear()
    from sts_engine.agent import build_graph

    engine = build_graph()
    cases = pick_cases(load_json(eval_path), max_cases)
    audited = [invoke_detailed_case(engine, case) for case in cases]
    return {
        "eval_file": display_path(eval_path),
        "cases": len(audited),
        "required_agents": REQUIRED_AGENTS,
        "valid_cases": sum(1 for item in audited if item["decision_valid"]),
        "cases_with_complete_trace": sum(1 for item in audited if not item["missing_agents"]),
        "cases_with_critic_warnings": sum(1 for item in audited if item["critic_warnings"]),
        "audits": audited,
    }


def format_trace_item(item: Dict[str, Any]) -> str:
    agent = item.get("agent", "UnknownAgent")
    details = []
    for key, value in item.items():
        if key == "agent":
            continue
        if isinstance(value, list):
            rendered = ", ".join(str(part) for part in value[:4])
            if len(value) > 4:
                rendered += ", ..."
        else:
            rendered = str(value)
        details.append(f"{key}={rendered}")
    return f"- **{agent}**: " + ("; ".join(details) if details else "completed")


def markdown_report(report: Dict[str, Any]) -> str:
    lines = [
        "# Agent Trace Audit",
        "",
        "This report expands representative recommendation cases into an interview-readable Multi-Agent trace.",
        "",
        f"- Eval file: `{display_path(report['eval_file'])}`",
        f"- Audited cases: {report['cases']}",
        f"- Valid decisions: {report['valid_cases']}/{report['cases']}",
        f"- Complete traces: {report['cases_with_complete_trace']}/{report['cases']}",
        f"- Cases with critic warnings: {report['cases_with_critic_warnings']}/{report['cases']}",
        "",
        "## Required Agent Contract",
        "",
    ]
    lines.extend(f"- {agent}" for agent in report["required_agents"])
    for audit in report["audits"]:
        top = audit["top"]
        runner_up = audit["runner_up"]
        warnings = ", ".join(audit["critic_warnings"]) or "none"
        missing = ", ".join(audit["missing_agents"]) or "none"
        grade = f" ({top['grade']})" if top["grade"] else ""
        lines.extend(
            [
                "",
                f"## Case: {audit['id']}",
                "",
                f"- Query type: `{audit['query_type']}`",
                f"- Scene type: `{audit['scene_type']}`",
                f"- Selected skill: `{audit['selected_skill']}`",
                f"- Decision valid: {audit['decision_valid']}",
                f"- Latency: {audit['latency_ms']} ms",
                f"- Expected top: `{audit['expected_top']}`",
                f"- Ranked Top-3: {', '.join(audit['ranked_top3'])}",
                f"- Critic warnings: {warnings}",
                f"- Missing agents: {missing}",
                "",
                "### Top Recommendation",
                "",
                f"- Option: `{top['option_id']}` / {top['name']}",
                f"- Score: {top['score']}{grade}, confidence {top['confidence']}",
                f"- Evidence count: {top['evidence_count']}",
            ]
        )
        if top["reasons"]:
            lines.append("- Reasons:")
            lines.extend(f"  - {reason}" for reason in top["reasons"])
        if top["risks"]:
            lines.append("- Risks:")
            lines.extend(f"  - {risk}" for risk in top["risks"])
        if runner_up["option_id"]:
            lines.extend(
                [
                    "",
                    "### Runner-Up Tradeoff",
                    "",
                    f"- Option: `{runner_up['option_id']}` / {runner_up['name']}",
                    f"- Score: {runner_up['score']}",
                    f"- Why not: {runner_up['why_not'] or 'No major drawback recorded.'}",
                ]
            )
        lines.extend(["", "### Agent Trace", ""])
        lines.extend(format_trace_item(item) for item in audit["agent_trace"])
    lines.extend(
        [
            "",
            "## Interview Takeaways",
            "",
            "- The workflow is observable: every recommendation records routing, retrieval, risk, scoring, critic, and explanation steps.",
            "- CriticAgent is a guardrail for stale scenes, empty options, and illegal recommendations; it reports warnings without crashing the Mod.",
            "- This trace format can be attached to replay payloads, turning subjective recommendation complaints into inspectable cases.",
            "",
        ]
    )
    return "\n".join(lines)


def compact_summary(report: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "cases": report["cases"],
        "valid_cases": report["valid_cases"],
        "complete_traces": report["cases_with_complete_trace"],
        "critic_warning_cases": report["cases_with_critic_warnings"],
        "case_ids": [item["id"] for item in report["audits"]],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate representative Multi-Agent trace audit examples.")
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--eval", default=str(DEFAULT_EVAL))
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--md-output", default=str(DEFAULT_MD_OUTPUT))
    parser.add_argument("--max-cases", type=int, default=6)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()

    report = build_report(Path(args.data), Path(args.eval), args.max_cases)
    printed = compact_summary(report) if args.summary_only else report
    print(json.dumps(printed, ensure_ascii=False, indent=2))
    if report["cases_with_complete_trace"] != report["cases"]:
        raise SystemExit("Agent trace audit found cases with missing agent nodes.")
    if not args.no_write:
        json_output = Path(args.json_output)
        md_output = Path(args.md_output)
        json_output.parent.mkdir(parents=True, exist_ok=True)
        md_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        md_output.write_text(markdown_report(report), encoding="utf-8")


if __name__ == "__main__":
    main()
