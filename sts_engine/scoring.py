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

VALID_OPTION_TYPES = {
    "card_pick": {"card", "unknown"},
    "relic_pick": {"relic", "unknown"},
    "shop": {"shop_action", "card", "relic", "potion", "unknown"},
    "pathing": {"path_node", "unknown"},
    "combat": {"card", "potion", "unknown"},
}


class RecommendationScorer:
    def __init__(self, knowledge_base: KnowledgeBase | None = None):
        self.kb = knowledge_base or load_knowledge_base()

    def score(self, state: Dict[str, Any], evidence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if state.get("query_type") == "pathing":
            return self._score_pathing(state)

        evidence_by_option: Dict[str, List[Dict[str, Any]]] = {}
        for item in evidence:
            evidence_by_option.setdefault(item["option_id"], []).append(item)

        risk_tags = self.kb.risk_tags(state)
        deck_tags = self._deck_tags(state)
        strategy_matches = self.kb.strategy_matches(state, state.get("options", []))
        query_type = state.get("query_type", "card_pick")
        scores = []
        for option in self.kb.option_entities(state.get("options", []), state.get("character_class", "").lower()):
            option_id = option["id"]
            option_tags = set(option.get("tags", []))
            option_evidence = evidence_by_option.get(option_id, [])
            option_strategy = strategy_matches.get(option_id, [])
            score = float(option.get("base_value", 35)) + QUERY_BONUSES.get(query_type, {}).get("base", 0)
            reasons: List[str] = []
            risks: List[str] = []
            valid = True

            legality_adjustment, legality_reason, legality_risk, valid = self._legality_adjustment(
                option, query_type, state
            )
            score += legality_adjustment
            if legality_reason:
                reasons.append(legality_reason)
            if legality_risk:
                risks.append(legality_risk)

            synergy_bonus = sum(self._synergy_weight(item) for item in option_evidence)
            if synergy_bonus:
                score += synergy_bonus
                mechanics = sorted({item["mechanic_name"] for item in option_evidence})
                reasons.append(f"Graph synergy with current run: {', '.join(mechanics)}.")

            strategy_bonus = min(36.0, sum(item.get("bonus", 0) for item in option_strategy))
            if strategy_bonus:
                score += strategy_bonus
                archetypes = sorted({item.get("archetype_name", "") for item in option_strategy if item.get("archetype_name")})
                if archetypes:
                    reasons.append(f"Archetype fit: {', '.join(archetypes)}.")
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
            raw_score = score
            display_score = self._display_score(raw_score)
            confidence = self._confidence(option, option_evidence, option_strategy, reasons, risks, valid)
            scores.append(
                {
                    "option_id": option_id,
                    "name": option.get("name", option_id),
                    "decision_type": query_type,
                    "valid": valid,
                    "score": display_score,
                    "raw_score": round(raw_score, 2),
                    "strategy_signal": round(strategy_bonus, 2),
                    "confidence": confidence,
                    "reasons": reasons[:4],
                    "risks": risks[:3],
                    "evidence": (option_evidence + option_strategy)[:8],
                }
            )

        scores.sort(
            key=lambda item: (
                -self._explicit_strategy_count(item.get("evidence", [])),
                -item.get("strategy_signal", 0),
                -item["score"],
                -len(item.get("evidence", [])),
                -item["confidence"],
                len(item.get("risks", [])),
                item["option_id"],
            )
        )
        return scores

    def _display_score(self, raw_score: float) -> float:
        if raw_score <= 100:
            return round(max(0.0, raw_score), 2)
        overflow = raw_score - 100
        return round(min(100.0, 100 - 28 / (1 + overflow / 28)), 2)

    def _score_pathing(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        risk_tags = self.kb.risk_tags(state)
        deck_tags = self._deck_tags(state)
        hp_ratio = state.get("current_hp", state.get("max_hp", 1)) / max(state.get("max_hp", 1), 1)
        character_class = state.get("character_class", "").lower()
        options = state.get("options", [])
        scored = []
        for raw_option in options:
            path = self._parse_path_option(str(raw_option))
            if len(path) == 1:
                entity = self.kb.get(path[0], character_class) or {"id": path[0], "name": str(raw_option), "base_value": 45, "tags": []}
                base_name = entity.get("name", str(raw_option))
                score = float(entity.get("base_value", 45))
            else:
                base_name = str(raw_option)
                score = 44.0 + len(path) * 2.0

            reasons: List[str] = []
            risks: List[str] = []
            counts = Counter(path)
            score += counts["treasure"] * 14
            score += counts["rest"] * (18 if "low_hp" in risk_tags else 8)
            score += counts["shop"] * self._shop_path_value(state)
            score += counts["monster"] * self._monster_path_value(state, deck_tags)
            score += counts["event"] * self._event_path_value(state, risk_tags)
            score += counts["unknown"] * self._event_path_value(state, risk_tags)
            score += counts["elite"] * self._elite_path_value(state, risk_tags, deck_tags, character_class)

            if counts["elite"]:
                if self._elite_ready(state, deck_tags, character_class):
                    reasons.append("Elite path is justified by current frontload, potions, HP, or a nearby rest site.")
                else:
                    risks.append("Elite path is risky without enough frontload damage, potion support, or HP.")
            if counts["elite"] >= 2 and counts["rest"] == 0:
                score -= 18
                risks.append("Forced multiple elites without a rest site is a high-variance route.")
            if counts["rest"]:
                if "low_hp" in risk_tags:
                    reasons.append("Rest site gives a recovery exit before the route becomes dangerous.")
                else:
                    reasons.append("Campfire keeps upgrade/rest flexibility open.")
            if counts["shop"]:
                if state.get("gold", 0) >= 150:
                    reasons.append("Gold total makes a shop route attractive.")
                elif character_class in {"silent", "defect"} and state.get("current_floor", 1) <= 8:
                    reasons.append("Early shop can buy frontload or potions for a weaker Act 1 start.")
                else:
                    risks.append("Shop value is limited when gold is low.")
            if counts["monster"] and state.get("current_floor", 1) <= 6:
                reasons.append("Early hallway fights are valuable for card rewards before committing to elites.")
            if counts["event"] or counts["unknown"]:
                if state.get("act", 1) >= 2:
                    reasons.append("Events gain value after Act 1 because they can avoid bad hallway fights.")
                else:
                    risks.append("Too many early Act 1 events can delay finding attack cards.")

            if not reasons:
                reasons.append("Route has acceptable baseline value, but no decisive pathing signal was found.")
            option_id = self._path_option_id(raw_option, path)
            raw_score = score
            scored.append(
                {
                    "option_id": option_id,
                    "name": base_name,
                    "decision_type": "pathing",
                    "valid": True,
                    "score": self._display_score(raw_score),
                    "raw_score": round(raw_score, 2),
                    "confidence": self._path_confidence(path, reasons, risks),
                    "reasons": reasons[:4],
                    "risks": risks[:3],
                    "evidence": [
                        {
                            "type": "pathing_rule",
                            "path": path,
                            "node_counts": dict(counts),
                            "risk_tags": risk_tags,
                            "deck_tags": deck_tags,
                            "source": "community_strategy_synthesis",
                            "source_url": "internal://strategy/pathing-rules",
                            "confidence": 0.72,
                        }
                    ],
                }
            )

        scored.sort(
            key=lambda item: (
                -item["score"],
                -item["confidence"],
                len(item.get("risks", [])),
                item["option_id"],
            )
        )
        return scored

    def _parse_path_option(self, option: str) -> List[str]:
        normalized = option.lower()
        for separator in ("->", ">", "/", "|", ","):
            normalized = normalized.replace(separator, "\n")
        aliases = {
            "?": "unknown",
            "unknown": "unknown",
            "event": "event",
            "monster": "monster",
            "fight": "monster",
            "hallway": "monster",
            "elite": "elite",
            "rest": "rest",
            "campfire": "rest",
            "rest_site": "rest",
            "shop": "shop",
            "merchant": "shop",
            "treasure": "treasure",
            "chest": "treasure",
        }
        path = []
        for part in normalized.splitlines():
            token = part.strip().replace(" ", "_").replace("-", "_")
            if not token:
                continue
            path.append(aliases.get(token, token))
        return path or [option]

    def _path_option_id(self, raw_option: str, path: List[str]) -> str:
        if len(path) == 1:
            resolved = self.kb.resolve_id(path[0])
            if resolved:
                return resolved
        return "path_" + "_".join(path).replace("?", "unknown")

    def _elite_ready(self, state: Dict[str, Any], deck_tags: List[str], character_class: str) -> bool:
        hp_ratio = state.get("current_hp", state.get("max_hp", 1)) / max(state.get("max_hp", 1), 1)
        frontload = deck_tags.count("frontload_damage") + deck_tags.count("aoe")
        defensive = deck_tags.count("block") + deck_tags.count("orb_frost")
        has_potion = bool(state.get("potions"))
        strong_act1_class = character_class in {"ironclad", "watcher"}
        return hp_ratio >= 0.62 and (frontload >= 3 or has_potion or strong_act1_class) and defensive >= 1

    def _elite_path_value(self, state: Dict[str, Any], risk_tags: List[str], deck_tags: List[str], character_class: str) -> float:
        if self._elite_ready(state, deck_tags, character_class):
            return 24.0 if state.get("act", 1) == 1 else 18.0
        penalty = -18.0
        if "low_hp" in risk_tags:
            penalty -= 12.0
        if deck_tags.count("frontload_damage") < 2:
            penalty -= 8.0
        return penalty

    def _shop_path_value(self, state: Dict[str, Any]) -> float:
        gold = state.get("gold", 0)
        if gold >= 180:
            return 22.0
        if gold >= 120:
            return 14.0
        if gold >= 75:
            return 6.0
        return -8.0

    def _monster_path_value(self, state: Dict[str, Any], deck_tags: List[str]) -> float:
        if state.get("act", 1) == 1 and state.get("current_floor", 1) <= 6:
            return 10.0
        if "low_hp" in self.kb.risk_tags(state):
            return -4.0
        return 4.0

    def _event_path_value(self, state: Dict[str, Any], risk_tags: List[str]) -> float:
        if state.get("act", 1) >= 2 or "low_hp" in risk_tags:
            return 8.0
        if state.get("current_floor", 1) <= 6:
            return -6.0
        return 3.0

    def _path_confidence(self, path: List[str], reasons: List[str], risks: List[str]) -> float:
        confidence = 0.46 + min(0.18, len(path) * 0.03) + min(0.18, len(reasons) * 0.04) - min(0.12, len(risks) * 0.04)
        return round(max(0.2, min(0.9, confidence)), 2)

    def _explicit_strategy_count(self, evidence: List[Dict[str, Any]]) -> int:
        return sum(1 for item in evidence if item.get("type") == "archetype_rule")

    def risk_report(self, state: Dict[str, Any]) -> Dict[str, Any]:
        risks = self.kb.risk_tags(state)
        return {
            "risks": risks,
            "summary": self._risk_summary(risks),
            "deck_tags": self._deck_tags(state),
        }

    def _deck_tags(self, state: Dict[str, Any]) -> List[str]:
        character_class = state.get("character_class", "").lower()
        deck_ids = self.kb.resolve_many(state.get("deck", []), character_class)
        relic_ids = self.kb.resolve_many(state.get("relics", []), character_class)
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
            if "low_hp" in risk_tags and "heal" in option_tags:
                score += 14
                reasons.append("Rest site is prioritized because current HP is low.")
            if "shop_ready" in risk_tags and "spend_gold" in option_tags:
                score += 10 if "low_hp" in risk_tags else 15
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

    def _legality_adjustment(
        self, option: Dict[str, Any], query_type: str, state: Dict[str, Any]
    ) -> tuple[float, str, str, bool]:
        entity_type = option.get("entity_type", "unknown")
        valid_types = VALID_OPTION_TYPES.get(query_type, {"unknown"})
        if entity_type not in valid_types:
            return (
                -60.0,
                "",
                f"{option.get('name', option.get('id', 'Option'))} is a {entity_type}, not a normal {query_type} option.",
                False,
            )

        if query_type == "shop" and "spend_gold" in option.get("tags", []) and state.get("gold", 0) < 75:
            return -12.0, "", "Gold is low, so paid shop actions are less attractive.", True
        if query_type == "pathing" and entity_type == "path_node" and option["id"] == "elite":
            if state.get("current_hp", state.get("max_hp", 1)) / max(state.get("max_hp", 1), 1) < 0.45:
                return -18.0, "", "Elite path is dangerous at the current HP total.", True
        return 0.0, "", "", True

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

    def _confidence(
        self,
        option: Dict[str, Any],
        evidence: List[Dict[str, Any]],
        strategy_matches: List[Dict[str, Any]],
        reasons: List[str],
        risks: List[str],
        valid: bool,
    ) -> float:
        evidence_confidences = []
        for item in evidence:
            evidence_confidences.append(float(item.get("owned_confidence", 0.5)))
            evidence_confidences.append(float(item.get("option_confidence", 0.5)))
        if evidence_confidences:
            evidence_quality = sum(evidence_confidences) / len(evidence_confidences)
        else:
            evidence_quality = float(option.get("confidence", 0.5))

        confidence = 0.34
        confidence += min(0.24, len(evidence) * 0.06)
        confidence += min(0.18, len(strategy_matches) * 0.09)
        confidence += min(0.12, len(reasons) * 0.03)
        confidence += max(0.0, min(0.14, (evidence_quality - 0.5) * 0.4))
        confidence -= min(0.12, len(risks) * 0.04)
        if option.get("entity_type") == "unknown":
            confidence -= 0.12
        if not valid:
            confidence -= 0.2
        return round(max(0.1, min(0.95, confidence)), 2)

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
