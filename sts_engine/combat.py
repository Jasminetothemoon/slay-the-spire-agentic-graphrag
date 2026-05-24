import re
from itertools import combinations
from typing import Any, Dict, List

from sts_engine.knowledge_base import KnowledgeBase, load_knowledge_base


class CombatAdvisor:
    """Deterministic shallow combat advisor for the first playable Mod MVP."""

    def __init__(self, knowledge_base: KnowledgeBase | None = None):
        self.kb = knowledge_base or load_knowledge_base()

    def advise(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        hand = self._hand_entities(state)
        if not hand:
            return []
        energy = int(state.get("energy", 3))
        incoming_damage = self._incoming_damage(state)
        enemies = state.get("enemies", [])
        candidates = []
        for sequence in self._legal_sequences(hand, energy):
            if not sequence:
                continue
            estimate = self._estimate_sequence(sequence, state)
            score = estimate["damage"] * 1.35 + estimate["block"] * 1.45 + estimate["utility"] * 8
            if incoming_damage > estimate["block"]:
                score -= min(22, (incoming_damage - estimate["block"]) * 0.8)
            if incoming_damage and estimate["block"] >= incoming_damage:
                score += 18
            if len(enemies) >= 2 and estimate["aoe"]:
                score += 16
            if self._can_likely_kill(enemies, estimate["damage"]):
                score += 20
            reasons = self._reasons(sequence, estimate, incoming_damage, enemies)
            risks = self._risks(sequence, estimate, incoming_damage)
            candidates.append(
                {
                    "option_id": "play_" + "_then_".join(card["id"] for card in sequence),
                    "name": " -> ".join(card["name"] for card in sequence),
                    "decision_type": "combat",
                    "valid": True,
                    "score": round(max(0.0, min(score, 100.0)), 2),
                    "confidence": self._confidence(sequence, state),
                    "reasons": reasons[:4],
                    "risks": risks[:3],
                    "evidence": [
                        {
                            "type": "combat_estimate",
                            "cards": [card["id"] for card in sequence],
                            "energy_cost": sum(card["cost"] for card in sequence),
                            "estimated_damage": estimate["damage"],
                            "estimated_block": estimate["block"],
                            "incoming_damage": incoming_damage,
                            "aoe": estimate["aoe"],
                        }
                    ],
                }
            )
        best_sequence_block = max(
            (
                item.get("evidence", [{}])[0].get("estimated_block", 0)
                for item in candidates
                if item.get("evidence", [{}])[0].get("type") == "combat_estimate"
            ),
            default=0,
        )
        candidates.extend(self._potion_candidates(state, incoming_damage, best_sequence_block))
        candidates.sort(key=lambda item: (-item["score"], -item["confidence"], item["option_id"]))
        return candidates[:5]

    def _hand_entities(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        character_class = state.get("character_class", "").lower()
        entities = []
        for card_name in state.get("hand_cards", []) or state.get("options", []):
            entity = self.kb.get(card_name, character_class)
            if not entity or entity.get("entity_type") != "card":
                continue
            card = dict(entity)
            card["cost"] = self._energy_cost(card)
            entities.append(card)
        return entities

    def _legal_sequences(self, hand: List[Dict[str, Any]], energy: int) -> List[List[Dict[str, Any]]]:
        sequences = []
        max_len = min(4, len(hand))
        for length in range(1, max_len + 1):
            for combo in combinations(hand, length):
                if sum(card["cost"] for card in combo) <= energy:
                    sequences.append(list(combo))
        return sequences

    def _estimate_sequence(self, sequence: List[Dict[str, Any]], state: Dict[str, Any]) -> Dict[str, Any]:
        damage = 0
        block = 0
        utility = 0
        aoe = False
        enemy_count = max(1, len(state.get("enemies", [])))
        for card in sequence:
            tags = set(card.get("tags", []))
            text = card.get("description", "")
            card_damage = self._first_number_after(text, "Deal")
            card_block = self._first_number_after(text, "Gain")
            if "frontload_damage" in tags and card_damage == 0:
                card_damage = 6
            if "block" in tags and card_block == 0:
                card_block = 5
            if "aoe" in tags:
                aoe = True
                damage += card_damage * min(enemy_count, 3)
            else:
                damage += card_damage
            block += card_block
            utility += len(tags.intersection({"weak", "vulnerable", "poison", "draw", "orb_frost", "orb_lightning"}))
        return {"damage": damage, "block": block, "utility": utility, "aoe": aoe}

    def _potion_candidates(self, state: Dict[str, Any], incoming_damage: int, best_sequence_block: int) -> List[Dict[str, Any]]:
        candidates = []
        for potion in state.get("potions", []):
            potion_lower = potion.lower()
            if incoming_damage >= 12 and "block" in potion_lower:
                score = 58.0
                if incoming_damage - best_sequence_block >= 12:
                    score += 14
                candidates.append(
                    {
                        "option_id": "use_" + potion_lower.replace(" ", "_"),
                        "name": f"Use {potion}",
                        "decision_type": "combat",
                        "valid": True,
                        "score": score,
                        "confidence": 0.62,
                        "reasons": ["Incoming damage is high enough that a defensive potion can preserve HP."],
                        "risks": ["Potion use spends a limited resource."],
                        "evidence": [{"type": "combat_potion", "incoming_damage": incoming_damage}],
                    }
                )
        return candidates

    def _incoming_damage(self, state: Dict[str, Any]) -> int:
        total = 0
        combat_state = state.get("combat_state", {})
        if isinstance(combat_state.get("incoming_damage"), int):
            return int(combat_state["incoming_damage"])
        for enemy in state.get("enemies", []):
            intent = str(enemy.get("intent", "")).lower()
            if "attack" in intent:
                total += int(enemy.get("intent_damage") or enemy.get("damage") or 0)
        return total

    def _energy_cost(self, card: Dict[str, Any]) -> int:
        cost = card.get("energy_cost")
        if isinstance(cost, int):
            return max(0, cost)
        return 1

    def _first_number_after(self, text: str, verb: str) -> int:
        match = re.search(rf"{verb}\s+(\d+)", text, re.IGNORECASE)
        return int(match.group(1)) if match else 0

    def _can_likely_kill(self, enemies: List[Dict[str, Any]], damage: int) -> bool:
        return any(damage >= int(enemy.get("hp", 999)) + int(enemy.get("block", 0)) for enemy in enemies)

    def _reasons(
        self, sequence: List[Dict[str, Any]], estimate: Dict[str, Any], incoming_damage: int, enemies: List[Dict[str, Any]]
    ) -> List[str]:
        reasons = [
            f"Estimated sequence output: {estimate['damage']} damage and {estimate['block']} block.",
        ]
        if incoming_damage and estimate["block"] >= incoming_damage:
            reasons.append("Covers the currently incoming damage.")
        if estimate["aoe"] and len(enemies) >= 2:
            reasons.append("AoE is valuable into the current multi-enemy board.")
        if self._can_likely_kill(enemies, estimate["damage"]):
            reasons.append("Likely removes at least one enemy this turn.")
        if any("weak" in card.get("tags", []) for card in sequence):
            reasons.append("Weak reduces incoming attack pressure.")
        return reasons

    def _risks(self, sequence: List[Dict[str, Any]], estimate: Dict[str, Any], incoming_damage: int) -> List[str]:
        risks = []
        if incoming_damage > estimate["block"]:
            risks.append(f"Leaves about {incoming_damage - estimate['block']} unblocked incoming damage.")
        if not any(card.get("type") == "Attack" for card in sequence) and estimate["damage"] == 0:
            risks.append("No direct damage in the proposed sequence.")
        return risks

    def _confidence(self, sequence: List[Dict[str, Any]], state: Dict[str, Any]) -> float:
        confidence = 0.46 + min(0.18, len(sequence) * 0.04)
        if state.get("combat_state", {}).get("incoming_damage") is not None:
            confidence += 0.1
        if state.get("enemies"):
            confidence += 0.08
        return round(min(0.78, confidence), 2)
