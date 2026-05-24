from collections import Counter
from typing import Any, Dict, List

from sts_engine.knowledge_base import KnowledgeBase, load_knowledge_base


QUERY_BONUSES = {
    "card_pick": {"base": 0, "skip_penalty": 0},
    "relic_pick": {"base": 4},
    "shop": {"base": 0},
    "pathing": {"base": 0},
    "combat": {"base": 0},
}


class RecommendationScorer:
    def __init__(self, knowledge_base: KnowledgeBase | None = None):
        self.kb = knowledge_base or load_knowledge_base()

    def score(self, state: Dict[str, Any], evidence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        evidence_by_option: Dict[str, List[Dict[str, Any]]] = {}
        for item in evidence:
            evidence_by_option.setdefault(item["option_id"], []).append(item)

        risk_tags = self.kb.risk_tags(state)
        deck_tags = self._deck_tags(state)
        strategy_matches = self.kb.strategy_matches(state, state.get("options", []))
        query_type = state.get("query_type", "card_pick")
        scores = []
        for option in self.kb.option_entities(state.get("options", [])):
            option_id = option["id"]
            option_tags = set(option.get("tags", []))
            option_evidence = evidence_by_option.get(option_id, [])
            option_strategy = strategy_matches.get(option_id, [])
            score = float(option.get("base_value", 35)) + QUERY_BONUSES.get(query_type, {}).get("base", 0)
            reasons: List[str] = []
            risks: List[str] = []

            synergy_bonus = sum(self._synergy_weight(item) for item in option_evidence)
            if synergy_bonus:
                score += synergy_bonus
                mechanics = sorted({item["mechanic_name"] for item in option_evidence})
                reasons.append(f"Graph synergy with current run: {', '.join(mechanics)}.")

            strategy_bonus = sum(item.get("bonus", 0) for item in option_strategy)
            if strategy_bonus:
                score += strategy_bonus
                reasons.extend(item["reason"] for item in option_strategy[:2])

            risk_bonus, risk_reasons = self._risk_adjustment(risk_tags, option_tags, query_type, state)
            score += risk_bonus
            reasons.extend(risk_reasons)

            curve_adjustment, curve_reason, curve_risk = self._curve_adjustment(option, state)
            score += curve_adjustment
            if curve_reason:
                reasons.append(curve_reason)
            if curve_risk:
                risks.append(curve_risk)

            class_adjustment, class_reason = self._class_adjustment(option, state)
            score += class_adjustment
            if class_reason:
                reasons.append(class_reason)

            redundancy_penalty = self._redundancy_penalty(option_tags, deck_tags)
            if redundancy_penalty:
                score -= redundancy_penalty
                risks.append("Adds to an already saturated package; marginal value may be lower.")

            if not reasons:
                reasons.append("Solid baseline value, but no decisive graph signal was found.")
            confidence = min(0.95, 0.42 + len(option_evidence) * 0.12 + len(reasons) * 0.05)
            scores.append(
                {
                    "option_id": option_id,
                    "name": option.get("name", option_id),
                    "score": round(max(0.0, min(score, 100.0)), 2),
                    "confidence": round(confidence, 2),
                    "reasons": reasons[:4],
                    "risks": risks[:3],
                    "evidence": (option_evidence + option_strategy)[:8],
                }
            )

        scores.sort(
            key=lambda item: (
                item["score"],
                len(item.get("evidence", [])),
                item["confidence"],
                -len(item.get("risks", [])),
            ),
            reverse=True,
        )
        return scores

    def risk_report(self, state: Dict[str, Any]) -> Dict[str, Any]:
        risks = self.kb.risk_tags(state)
        return {
            "risks": risks,
            "summary": self._risk_summary(risks),
            "deck_tags": self._deck_tags(state),
        }

    def _deck_tags(self, state: Dict[str, Any]) -> List[str]:
        deck_ids = self.kb.resolve_many(state.get("deck", []))
        relic_ids = self.kb.resolve_many(state.get("relics", []))
        return self.kb.tags_for_ids(deck_ids + relic_ids)

    def _risk_adjustment(
        self, risk_tags: List[str], option_tags: set[str], query_type: str, state: Dict[str, Any]
    ) -> tuple[float, List[str]]:
        score = 0.0
        reasons = []
        if "no_aoe" in risk_tags and "aoe" in option_tags:
            score += 18
            reasons.append("Fixes an AoE weakness before multi-enemy fights.")
        if "low_defense" in risk_tags and ({"block", "orb_frost", "defense"} & option_tags):
            score += 16
            reasons.append("Improves a low-defense deck profile.")
        if "slow_scaling" in risk_tags and "scaling_damage" in option_tags:
            score += 14
            reasons.append("Adds scaling for midgame and boss fights.")
        if "low_hp" in risk_tags and ({"block", "elite_safety", "heal"} & option_tags):
            score += 12
            reasons.append("Current HP is low, so safety is weighted higher.")
        if query_type == "pathing":
            if "low_hp" in risk_tags and "risk" in option_tags:
                score -= 20
                reasons.append("Low HP makes this route riskier.")
            if "shop_ready" in risk_tags and "spend_gold" in option_tags:
                score += 15
                reasons.append("Gold total makes a shop route attractive.")
        if query_type == "shop":
            if "deck_control" in option_tags and len(state.get("deck", [])) >= 12:
                score += 10
                reasons.append("Card removal improves deck consistency.")
            if "elite_safety" in option_tags and state.get("current_floor", 1) <= 15:
                score += 8
                reasons.append("Potion value is high before early elites.")
        return score, reasons

    def _curve_adjustment(self, option: Dict[str, Any], state: Dict[str, Any]) -> tuple[float, str, str]:
        energy_cost = option.get("energy_cost")
        if energy_cost is None:
            return 0.0, "", ""
        act = state.get("act", 1)
        deck_size = len(state.get("deck", []))
        if act == 1 and energy_cost >= 2 and deck_size < 12 and "aoe" not in option.get("tags", []):
            return -5.0, "", "Expensive early card may slow the deck unless it solves a specific fight."
        if energy_cost == 0 and "draw" in option.get("tags", []):
            return 4.0, "Low-cost consistency is valuable in tight turns.", ""
        return 0.0, "", ""

    def _class_adjustment(self, option: Dict[str, Any], state: Dict[str, Any]) -> tuple[float, str]:
        option_class = option.get("class")
        character_class = state.get("character_class", "").lower()
        if option_class in (None, "any"):
            return 0.0, ""
        if option_class == character_class:
            return 3.0, "Matches the current character card pool."
        if option.get("entity_type") == "card":
            return -45.0, "Off-class card detected; likely invalid unless a modded run allows it."
        return 0.0, ""

    def _synergy_weight(self, item: Dict[str, Any]) -> float:
        base = item.get("weight", 0.5) * 18
        option_rel = item.get("option_relationship")
        owned_rel = item.get("owned_relationship")
        mechanic = item.get("mechanic")
        if option_rel == "SCALES_WITH":
            base += 10
        if option_rel == "ENHANCES":
            base += 6
        if owned_rel in {"APPLIES", "ENHANCES"} and mechanic in {"poison", "strength", "focus", "orb_frost", "orb_lightning"}:
            base += 4
        return base

    def _redundancy_penalty(self, option_tags: set[str], deck_tags: List[str]) -> float:
        if not option_tags:
            return 0.0
        tag_counts = Counter(deck_tags)
        saturated = sum(1 for tag in option_tags if tag_counts[tag] >= 5)
        return float(saturated * 3)

    def _risk_summary(self, risks: List[str]) -> str:
        if not risks:
            return "No major deck-shape risk detected."
        labels = {
            "no_aoe": "missing AoE",
            "low_defense": "low defense",
            "slow_scaling": "limited scaling",
            "low_hp": "low HP",
            "shop_ready": "enough gold for shop value",
        }
        return "Detected: " + ", ".join(labels.get(risk, risk) for risk in risks) + "."
