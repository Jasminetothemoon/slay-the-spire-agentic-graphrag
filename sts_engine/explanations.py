from collections import Counter
from typing import Any, Dict, List

from sts_engine.knowledge_base import KnowledgeBase, load_knowledge_base


def build_explanation_panel(state: Dict[str, Any], kb: KnowledgeBase | None = None) -> Dict[str, Any]:
    kb = kb or load_knowledge_base()
    scores = state.get("option_scores", [])
    best = scores[0] if scores else {}
    risk_report = state.get("risk_report", {})
    deck_tags = risk_report.get("deck_tags") or _deck_tags(state, kb)
    archetypes = _archetype_fits(scores)
    graph_links = _graph_links(best)
    risk_coverage = _risk_coverage(best, risk_report)
    comparison = _candidate_comparison(scores)
    return {
        "summary": _summary(best, archetypes, risk_report),
        "current_plan": {
            "character_class": state.get("character_class", ""),
            "query_type": state.get("query_type", ""),
            "detected_archetypes": archetypes,
            "deck_tags": deck_tags[:12],
            "risk_tags": risk_report.get("risks", []),
            "risk_summary": risk_report.get("summary", ""),
        },
        "why_pick": {
            "option_id": best.get("option_id", ""),
            "name": best.get("name", ""),
            "score": best.get("score", 0),
            "confidence": best.get("confidence", 0),
            "main_reasons": best.get("reasons", [])[:4],
            "tradeoff": _tradeoff(best, top=best, rank=1),
        },
        "risk_coverage": risk_coverage,
        "graph_evidence": graph_links,
        "candidate_comparison": comparison,
    }


def _deck_tags(state: Dict[str, Any], kb: KnowledgeBase) -> List[str]:
    character_class = state.get("character_class", "").lower()
    deck_ids = kb.resolve_many(state.get("deck", []), character_class)
    relic_ids = kb.resolve_many(state.get("relics", []), character_class)
    return kb.tags_for_ids(deck_ids + relic_ids)


def _archetype_fits(scores: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    archetypes: Dict[str, Dict[str, Any]] = {}
    for score in scores:
        for item in score.get("evidence", []):
            archetype_id = item.get("archetype_id")
            if not archetype_id:
                continue
            entry = archetypes.setdefault(
                archetype_id,
                {
                    "id": archetype_id,
                    "name": item.get("archetype_name", archetype_id),
                    "matched_options": [],
                    "rules": [],
                    "total_bonus": 0.0,
                },
            )
            option_id = score.get("option_id")
            if option_id and option_id not in entry["matched_options"]:
                entry["matched_options"].append(option_id)
            rule_id = item.get("rule_id") or item.get("risk")
            if rule_id and rule_id not in entry["rules"]:
                entry["rules"].append(rule_id)
            entry["total_bonus"] += float(item.get("bonus", 0))
    return sorted(archetypes.values(), key=lambda item: (-item["total_bonus"], item["id"]))[:3]


def _graph_links(score: Dict[str, Any]) -> List[Dict[str, Any]]:
    links = []
    seen = set()
    for item in score.get("evidence", []):
        if item.get("type") != "shared_mechanic":
            continue
        key = (item.get("owned_id"), item.get("option_id"), item.get("mechanic"))
        if key in seen:
            continue
        seen.add(key)
        links.append(
            {
                "owned_id": item.get("owned_id"),
                "owned_name": item.get("owned_name"),
                "option_id": item.get("option_id"),
                "option_name": item.get("option_name"),
                "mechanic": item.get("mechanic"),
                "mechanic_name": item.get("mechanic_name"),
                "relationship": f"{item.get('owned_relationship', '')}->{item.get('option_relationship', '')}",
                "weight": item.get("weight", 0),
                "confidence": round(
                    (float(item.get("owned_confidence", 0.5)) + float(item.get("option_confidence", 0.5))) / 2,
                    3,
                ),
            }
        )
    return sorted(links, key=lambda item: (-float(item["weight"]), str(item["mechanic"])))[:6]


def _risk_coverage(score: Dict[str, Any], risk_report: Dict[str, Any]) -> List[Dict[str, str]]:
    risks = risk_report.get("risks", [])
    reasons = " ".join(score.get("reasons", []))
    coverage = []
    mapping = {
        "no_aoe": ("aoe", "Recommended option helps cover missing AoE."),
        "low_defense": ("defense", "Recommended option improves defensive consistency."),
        "slow_scaling": ("scaling", "Recommended option improves scaling for later fights."),
        "low_hp": ("safety", "Recommendation prioritizes safety because HP is low."),
        "shop_ready": ("gold", "Recommendation can convert current gold into power."),
    }
    for risk in risks:
        keyword, explanation = mapping.get(risk, (risk, "Recommendation addresses a detected run risk."))
        status = "covered" if keyword.lower() in reasons.lower() or risk in reasons else "monitor"
        coverage.append({"risk": risk, "status": status, "explanation": explanation})
    return coverage


def _candidate_comparison(scores: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not scores:
        return []
    top = scores[0]
    rows = []
    for rank, score in enumerate(scores[:5], start=1):
        evidence_types = Counter(item.get("type", "unknown") for item in score.get("evidence", []))
        rows.append(
            {
                "rank": rank,
                "option_id": score.get("option_id"),
                "name": score.get("name"),
                "score": score.get("score"),
                "confidence": score.get("confidence"),
                "delta_from_top": round(float(top.get("score", 0)) - float(score.get("score", 0)), 2),
                "strategy_matches": sum(
                    evidence_types.get(kind, 0)
                    for kind in ("archetype_rule", "preferred_archetype", "preferred_archetype_rule", "risk_cover")
                ),
                "graph_matches": evidence_types.get("shared_mechanic", 0),
                "risks": score.get("risks", [])[:2],
                "best_reason": (score.get("reasons") or [""])[0],
                "why_not": _tradeoff(score, top=top, rank=rank),
            }
        )
    return rows


def _tradeoff(score: Dict[str, Any], top: Dict[str, Any], rank: int) -> str:
    if not score:
        return ""
    if rank == 1:
        risks = score.get("risks") or []
        if risks:
            return "Top option, but monitor its listed risk before committing."
        return "Best overall mix of score, confidence, strategy fit, and graph evidence."

    gap = round(float(top.get("score", 0)) - float(score.get("score", 0)), 2)
    evidence = score.get("evidence", []) or []
    evidence_types = Counter(item.get("type", "unknown") for item in evidence)
    risks = score.get("risks") or []
    if gap >= 12:
        return f"Lower priority because it trails the top option by {gap} points."
    if not evidence:
        return "Lower priority because it has weaker graph or strategy evidence for the current run."
    strategy_count = sum(
        evidence_types.get(kind, 0)
        for kind in ("archetype_rule", "preferred_archetype", "preferred_archetype_rule", "risk_cover")
    )
    if strategy_count == 0:
        return "Lower priority because it does not clearly advance the detected archetype or cover a major risk."
    if risks:
        return f"Lower priority because of this risk: {risks[0]}"
    return "Playable alternative, but its current-run payoff is less direct than the top recommendation."


def _summary(best: Dict[str, Any], archetypes: List[Dict[str, Any]], risk_report: Dict[str, Any]) -> str:
    if not best:
        return "No scored recommendation is available."
    pieces = [f"Pick {best.get('name', best.get('option_id', 'the top option'))}."]
    if archetypes:
        pieces.append(f"Primary archetype signal: {archetypes[0]['name']}.")
    if risk_report.get("summary"):
        pieces.append(risk_report["summary"])
    return " ".join(pieces)
