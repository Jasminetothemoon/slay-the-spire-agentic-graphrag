import time
from typing import Any, Dict

try:
    from langgraph.graph import END, StateGraph
except Exception:
    END = None
    StateGraph = None

from sts_engine.retriever import GraphRAGRetriever
from sts_engine.scoring import RecommendationScorer
from sts_engine.combat import CombatAdvisor
from sts_engine.state import RunState


retriever = GraphRAGRetriever()
scorer = RecommendationScorer(retriever.kb)
combat_advisor = CombatAdvisor(retriever.kb)


def validate_state_node(state: RunState) -> Dict[str, Any]:
    errors = []
    if not state.get("run_id"):
        errors.append("Missing run_id.")
    if not state.get("character_class"):
        errors.append("Missing character_class.")
    if not state.get("query_type"):
        errors.append("Missing query_type.")
    if not state.get("options") and state.get("query_type") != "combat":
        errors.append("No decision options were provided.")
    return {"validation_errors": errors, "_started_at": time.perf_counter()}


def retrieve_context_node(state: RunState) -> Dict[str, Any]:
    if state.get("validation_errors"):
        return {"graph_context": []}
    return {"graph_context": retriever.retrieve(state)}


def risk_assessment_node(state: RunState) -> Dict[str, Any]:
    return {"risk_report": scorer.risk_report(state)}


def score_options_node(state: RunState) -> Dict[str, Any]:
    if state.get("validation_errors"):
        return {"option_scores": []}
    if state.get("query_type") == "combat":
        return {"option_scores": combat_advisor.advise(state)}
    option_scores = scorer.score(state, state.get("graph_context", []))
    return {"option_scores": option_scores}


def explain_decision_node(state: RunState) -> Dict[str, Any]:
    started_at = state.get("_started_at", time.perf_counter())
    errors = state.get("validation_errors", [])
    if errors:
        return {
            "recommendation": "invalid_state",
            "reasoning": "Cannot recommend because: " + "; ".join(errors),
            "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
        }

    scores = state.get("option_scores", [])
    if not scores:
        return {
            "recommendation": "skip",
            "reasoning": "No options could be scored. Prefer skipping or using manual review.",
            "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
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
        "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
    }


def build_graph():
    if StateGraph is None:
        return SequentialAgent()
    workflow = StateGraph(RunState)
    workflow.add_node("validate_state", validate_state_node)
    workflow.add_node("retrieve_context", retrieve_context_node)
    workflow.add_node("assess_risk", risk_assessment_node)
    workflow.add_node("score_options", score_options_node)
    workflow.add_node("explain_decision", explain_decision_node)

    workflow.set_entry_point("validate_state")
    workflow.add_edge("validate_state", "retrieve_context")
    workflow.add_edge("retrieve_context", "assess_risk")
    workflow.add_edge("assess_risk", "score_options")
    workflow.add_edge("score_options", "explain_decision")
    workflow.add_edge("explain_decision", END)
    return workflow.compile()


class SequentialAgent:
    """Dependency-light fallback used when LangGraph is not installed."""

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        current = dict(state)
        for node in (
            validate_state_node,
            retrieve_context_node,
            risk_assessment_node,
            score_options_node,
            explain_decision_node,
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
