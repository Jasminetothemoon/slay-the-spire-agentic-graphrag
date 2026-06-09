import time
from typing import Any, Dict, List

try:
    from langgraph.graph import END, StateGraph
except Exception:
    END = None
    StateGraph = None

from sts_engine.combat import CombatAdvisor
from sts_engine.explanations import build_explanation_panel
from sts_engine.retriever import GraphRAGRetriever
from sts_engine.scoring import RecommendationScorer
from sts_engine.skills import SkillRegistry, build_default_registry
from sts_engine.state import RunState


retriever = GraphRAGRetriever()
scorer = RecommendationScorer(retriever.kb)
combat_advisor = CombatAdvisor(retriever.kb)
skill_registry = build_default_registry(scorer, retriever, combat_advisor)


def append_trace(state: RunState, agent: str, detail: Dict[str, Any]) -> List[Dict[str, Any]]:
    return list(state.get("agent_trace", [])) + [{"agent": agent, **detail}]


def scene_type_for_state(state: Dict[str, Any]) -> str:
    query_type = state.get("query_type", "")
    current_screen = str(state.get("current_screen") or "").upper()
    if query_type == "card_pick":
        return "card_reward"
    if query_type == "shop":
        return "shop"
    if query_type == "pathing":
        return "map"
    if query_type == "combat":
        return "combat"
    if query_type == "rest_site":
        return "rest_site"
    if query_type == "smith":
        return "smith"
    if query_type == "relic_pick":
        return "boss_relic" if "BOSS" in current_screen else "relic_reward"
    return query_type or "unknown"


def state_agent_node(state: RunState) -> Dict[str, Any]:
    started = state.get("_started_at", time.perf_counter())
    scene_type = scene_type_for_state(state)
    errors = []
    if not state.get("run_id"):
        errors.append("Missing run_id.")
    if not state.get("character_class"):
        errors.append("Missing character_class.")
    if not state.get("query_type"):
        errors.append("Missing query_type.")
    return {
        "_started_at": started,
        "scene_type": scene_type,
        "validation_errors": errors,
        "agent_trace": append_trace(state, "StateAgent", {"scene_type": scene_type, "errors": len(errors)}),
    }


def scene_router_agent_node(state: RunState) -> Dict[str, Any]:
    skill = skill_registry.select(state)
    options = skill.build_options(state)
    errors = list(state.get("validation_errors", []))
    if not options and state.get("query_type") != "combat" and state.get("scene_type") != "map":
        errors.append("No decision options were provided.")
    return {
        "selected_skill": skill.id,
        "skill_options": options,
        "validation_errors": errors,
        "agent_trace": append_trace(
            state,
            "SceneRouterAgent",
            {"selected_skill": skill.id, "options_count": len(options)},
        ),
    }


def retrieval_agent_node(state: RunState) -> Dict[str, Any]:
    if state.get("_ablation_disable_graph") or state.get("validation_errors"):
        context: List[Dict[str, Any]] = []
    else:
        skill = skill_registry.select(state)
        context = skill.retrieve_context(state, state.get("skill_options", []))
    return {
        "graph_context": context,
        "agent_trace": append_trace(state, "RetrievalAgent", {"context_count": len(context)}),
    }


def risk_agent_node(state: RunState) -> Dict[str, Any]:
    risk_report = scorer.risk_report(state)
    risks = risk_report.get("risks", [])
    return {
        "risk_report": risk_report,
        "agent_trace": append_trace(state, "RiskAgent", {"risks": risks[:6]}),
    }


def skill_scoring_agent_node(state: RunState) -> Dict[str, Any]:
    if state.get("validation_errors"):
        scores: List[Dict[str, Any]] = []
    else:
        skill = skill_registry.select(state)
        scores = skill.score(state, state.get("skill_options", []), state.get("graph_context", []))
    return {
        "option_scores": scores,
        "agent_trace": append_trace(state, "SkillScoringAgent", {"scores": len(scores), "selected_skill": state.get("selected_skill", "")}),
    }


def critic_agent_node(state: RunState) -> Dict[str, Any]:
    if state.get("_ablation_disable_critic"):
        return {
            "critic_warnings": [],
            "decision_valid": bool(state.get("option_scores")),
            "agent_trace": append_trace(state, "CriticAgent", {"warnings": 0, "decision_valid": bool(state.get("option_scores")), "disabled": True}),
        }
    warnings = []
    errors = state.get("validation_errors", [])
    scores = state.get("option_scores", [])
    options = state.get("skill_options", state.get("options", [])) or []
    query_type = state.get("query_type", "")
    scene_type = state.get("scene_type", "")
    if errors:
        warnings.extend(errors)
    if not scores:
        warnings.append("No option scores were produced.")
    if scores and options and query_type not in {"combat", "pathing"}:
        option_names = {str(option).lower() for option in options}
        top = scores[0]
        if str(top.get("name", "")).lower() not in option_names and str(top.get("option_id", "")).lower() not in option_names:
            warnings.append("Top recommendation did not directly match the submitted option labels.")
    if query_type == "combat" and scene_type != "combat":
        warnings.append("Combat query is not aligned with the detected scene.")
    if query_type in {"card_pick", "relic_pick", "shop", "pathing"} and scene_type == "combat":
        warnings.append("Non-combat query appears to be attached to a combat scene.")
    return {
        "critic_warnings": warnings,
        "decision_valid": not errors and bool(scores),
        "agent_trace": append_trace(state, "CriticAgent", {"warnings": len(warnings), "decision_valid": not errors and bool(scores)}),
    }


def explainer_agent_node(state: RunState) -> Dict[str, Any]:
    started_at = state.get("_started_at", time.perf_counter())
    errors = state.get("validation_errors", [])
    if errors:
        return {
            "recommendation": "invalid_state",
            "reasoning": "Cannot recommend because: " + "; ".join(errors),
            "explanation_panel": {},
            "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
            "agent_trace": append_trace(state, "ExplainerAgent", {"recommendation": "invalid_state"}),
        }

    scores = state.get("option_scores", [])
    if not scores:
        return {
            "recommendation": "skip",
            "reasoning": "No options could be scored. Prefer skipping or using manual review.",
            "explanation_panel": {},
            "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
            "agent_trace": append_trace(state, "ExplainerAgent", {"recommendation": "skip"}),
        }

    best = scores[0]
    risk_summary = state.get("risk_report", {}).get("summary", "")
    reason_lines = [
        f"Recommended: {best['name']} (score {best['score']}, confidence {best['confidence']}).",
        risk_summary,
    ]
    reason_lines.extend(best.get("reasons", [])[:3])
    if best.get("risks"):
        reason_lines.append("Risks: " + " ".join(best["risks"]))
    return {
        "recommendation": best["option_id"],
        "reasoning": " ".join(line for line in reason_lines if line),
        "explanation_panel": build_explanation_panel(state, scorer.kb),
        "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
        "agent_trace": append_trace(state, "ExplainerAgent", {"recommendation": best["option_id"]}),
    }


def build_graph():
    if StateGraph is None:
        return SequentialAgent()
    workflow = StateGraph(RunState)
    workflow.add_node("StateAgent", state_agent_node)
    workflow.add_node("SceneRouterAgent", scene_router_agent_node)
    workflow.add_node("RetrievalAgent", retrieval_agent_node)
    workflow.add_node("RiskAgent", risk_agent_node)
    workflow.add_node("SkillScoringAgent", skill_scoring_agent_node)
    workflow.add_node("CriticAgent", critic_agent_node)
    workflow.add_node("ExplainerAgent", explainer_agent_node)

    workflow.set_entry_point("StateAgent")
    workflow.add_edge("StateAgent", "SceneRouterAgent")
    workflow.add_edge("SceneRouterAgent", "RetrievalAgent")
    workflow.add_edge("RetrievalAgent", "RiskAgent")
    workflow.add_edge("RiskAgent", "SkillScoringAgent")
    workflow.add_edge("SkillScoringAgent", "CriticAgent")
    workflow.add_edge("CriticAgent", "ExplainerAgent")
    workflow.add_edge("ExplainerAgent", END)
    return workflow.compile()


class SequentialAgent:
    """Dependency-light fallback used when LangGraph is not installed."""

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        current = dict(state)
        for node in (
            state_agent_node,
            scene_router_agent_node,
            retrieval_agent_node,
            risk_agent_node,
            skill_scoring_agent_node,
            critic_agent_node,
            explainer_agent_node,
        ):
            current.update(node(current))
        return current


def recommend(state: Dict[str, Any]) -> Dict[str, Any]:
    return build_graph().invoke(state)


if __name__ == "__main__":
    demo_state = {
        "run_id": "demo_001",
        "source": "manual",
        "character_class": "silent",
        "ascension_level": 20,
        "act": 1,
        "current_floor": 10,
        "current_hp": 40,
        "max_hp": 70,
        "gold": 120,
        "deck": ["Strike", "Defend", "Deadly Poison", "Bouncing Flask"],
        "relics": ["Snecko Skull"],
        "potions": [],
        "query_type": "card_pick",
        "options": ["Catalyst", "Backflip", "Dagger Spray"],
        "user_query": "Which card should I pick?",
    }
    result = recommend(demo_state)
    print(result["recommendation"])
    print(result["reasoning"])
