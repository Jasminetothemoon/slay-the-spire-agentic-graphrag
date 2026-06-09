from __future__ import annotations

from typing import Any, Dict, List, Set

from sts_engine.combat import CombatAdvisor
from sts_engine.retriever import GraphRAGRetriever
from sts_engine.scoring import RecommendationScorer
from sts_engine.skills.base import DecisionSkill


class ScoringSkill(DecisionSkill):
    id = "generic_scoring_skill"
    query_types: Set[str] = set()

    def __init__(self, scorer: RecommendationScorer, retriever: GraphRAGRetriever):
        self.scorer = scorer
        self.retriever = retriever

    def retrieve_context(self, state: Dict[str, Any], options: List[Any]) -> List[Dict[str, Any]]:
        if not options and state.get("query_type") != "pathing":
            return []
        current_state = dict(state)
        current_state["options"] = options
        return self.retriever.retrieve(current_state)

    def score(self, state: Dict[str, Any], options: List[Any], context: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        current_state = dict(state)
        current_state["options"] = options
        return self.scorer.score(current_state, context)


class CardPickSkill(ScoringSkill):
    id = "card_pick_skill"
    query_types = {"card_pick"}


class RelicPickSkill(ScoringSkill):
    id = "relic_pick_skill"
    query_types = {"relic_pick"}


class ShopSkill(ScoringSkill):
    id = "shop_skill"
    query_types = {"shop"}


class PathingSkill(ScoringSkill):
    id = "pathing_skill"
    query_types = {"pathing"}

    def build_options(self, state: Dict[str, Any]) -> List[Any]:
        options = list(state.get("options") or [])
        if not options:
            options = list(state.get("map_options") or [])
        return options

    def retrieve_context(self, state: Dict[str, Any], options: List[Any]) -> List[Dict[str, Any]]:
        return []


class CombatSkill(DecisionSkill):
    id = "combat_skill"
    query_types = {"combat"}

    def __init__(self, combat_advisor: CombatAdvisor):
        self.combat_advisor = combat_advisor

    def build_options(self, state: Dict[str, Any]) -> List[Any]:
        return list(state.get("options") or state.get("hand_cards") or [])

    def score(self, state: Dict[str, Any], options: List[Any], context: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        current_state = dict(state)
        current_state["options"] = options
        return self.combat_advisor.advise(current_state)


class RestSiteSkill(DecisionSkill):
    id = "rest_site_skill"
    query_types = {"rest_site", "smith"}

    def build_options(self, state: Dict[str, Any]) -> List[Any]:
        return list(state.get("options") or ["Rest", "Smith"])

    def score(self, state: Dict[str, Any], options: List[Any], context: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        hp = float(state.get("current_hp", 0) or 0)
        max_hp = float(state.get("max_hp", 1) or 1)
        hp_ratio = hp / max(max_hp, 1.0)
        scores = []
        for raw in options:
            name = str(raw)
            option_id = name.lower().replace(" ", "_")
            is_rest = option_id in {"rest", "heal"}
            score = 70.0 if is_rest and hp_ratio < 0.45 else 58.0
            if not is_rest and hp_ratio >= 0.55:
                score = 72.0
            reasons = ["Low HP makes resting valuable."] if is_rest and hp_ratio < 0.45 else ["Upgrade value is preferred when HP is stable."]
            risks = [] if hp_ratio >= 0.45 or is_rest else ["Skipping rest can be risky at low HP."]
            scores.append(
                {
                    "option_id": option_id,
                    "name": name,
                    "decision_type": "rest_site",
                    "valid": True,
                    "score": round(score, 2),
                    "raw_score": round(score, 2),
                    "confidence": 0.68,
                    "reasons": reasons,
                    "risks": risks,
                    "evidence": [
                        {
                            "type": "rest_site_rule",
                            "hp_ratio": round(hp_ratio, 3),
                            "source": "internal://skills/rest-site",
                            "confidence": 0.68,
                        }
                    ],
                }
            )
        return sorted(scores, key=lambda item: (-item["score"], item["option_id"]))
