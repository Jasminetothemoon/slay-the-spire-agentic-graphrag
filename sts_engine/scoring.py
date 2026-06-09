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

        query_type = state.get("query_type", "card_pick")
        current_options = self._options_for_query(state.get("options", []), query_type)
        state = dict(state)
        state["options"] = current_options
        evidence_by_option: Dict[str, List[Dict[str, Any]]] = {}
        for item in evidence:
            evidence_by_option.setdefault(item["option_id"], []).append(item)

        risk_tags = [] if state.get("_ablation_disable_risk") else self.kb.risk_tags(state)
        deck_tags = self._deck_tags(state)
        strategy_matches = {} if state.get("_ablation_disable_strategy") else self.kb.strategy_matches(state, current_options)
        shop_context = self._shop_context_by_option(state)
        scene_type = str(state.get("scene_type") or "").lower()
        scores = []
        for option in self.kb.option_entities(current_options, state.get("character_class", "").lower()):
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

            shop_adjustment, shop_reason, shop_risk = self._shop_item_adjustment(
                option, query_type, state, shop_context.get(option_id)
            )
            score += shop_adjustment
            if shop_reason:
                reasons.append(shop_reason)
            if shop_risk:
                risks.append(shop_risk)

            skip_adjustment, skip_reason, skip_risk = self._skip_card_adjustment(option, query_type, state)
            score += skip_adjustment
            if skip_reason:
                reasons.append(skip_reason)
            if skip_risk:
                risks.append(skip_risk)

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

            relic_adjustment, relic_reasons, relic_risks, relic_evidence = self._relic_context_adjustment(
                option, query_type, state, deck_tags, risk_tags, scene_type
            )
            score += relic_adjustment
            reasons.extend(relic_reasons)
            risks.extend(relic_risks)
            if relic_evidence:
                option_evidence = option_evidence + relic_evidence

            redundancy_penalty = self._redundancy_penalty(option_tags, deck_tags)
            if redundancy_penalty:
                score -= redundancy_penalty
                risks.append("Adds to an already saturated package; marginal value may be lower.")

            if not reasons:
                reasons.append("Solid baseline value, but no decisive graph signal was found.")
            raw_score = score
            display_score = self._display_score(raw_score)
            confidence = self._confidence(option, option_evidence, option_strategy, reasons, risks, valid)
            score_item = {
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
            context = shop_context.get(option_id)
            if query_type == "shop" and context:
                score_item["shop_item_type"] = str(context.get("item_type", ""))
                score_item["shop_price"] = int(context.get("price") or 0)
                score_item["shop_affordable"] = bool(context.get("affordable", True))
            scores.append(score_item)

        self._apply_skip_card_context(scores, query_type, state)
        scores.sort(
            key=lambda item: (
                not item.get("valid", True),
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

    def _options_for_query(self, options: List[Any], query_type: str) -> List[Any]:
        if query_type != "shop":
            return list(options)
        normalized = []
        for option in options:
            if str(option).strip().lower().replace(" ", "_").replace("-", "_") in {"skip", "skip_card"}:
                normalized.append("skip_shop")
            else:
                normalized.append(option)
        return normalized

    def _shop_context_by_option(self, state: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        character_class = state.get("character_class", "").lower()
        context: Dict[str, Dict[str, Any]] = {}
        for item in state.get("shop_items", []) or []:
            if not isinstance(item, dict):
                continue
            raw_id = str(item.get("id") or item.get("name") or "")
            option_id = self.kb.resolve_id(raw_id, character_class) or raw_id
            if option_id:
                context[option_id] = item
            normalized_name = str(item.get("name") or "").strip().lower().replace(" ", "_").replace("-", "_")
            if normalized_name == "remove_a_card":
                context["remove_card"] = item
            item_type = str(item.get("item_type") or "").lower()
            if item_type == "card":
                context.setdefault("buy_card", item)
            elif item_type == "relic":
                context.setdefault("buy_relic", item)
            elif item_type == "potion":
                context.setdefault("buy_potion", item)
            elif item_type == "remove":
                context.setdefault("remove_card", item)
        return context

    def _shop_item_adjustment(
        self, option: Dict[str, Any], query_type: str, state: Dict[str, Any], context: Dict[str, Any] | None
    ) -> tuple[float, str, str]:
        if query_type != "shop" or not context:
            return 0.0, "", ""
        price = int(context.get("price") or 0)
        affordable = bool(context.get("affordable", True))
        item_type = str(context.get("item_type") or option.get("entity_type", "")).lower()
        gold = int(state.get("gold", 0) or 0)
        if not affordable or (price and price > gold):
            return -90.0, "", f"Cannot afford this shop option: costs {price} gold with {gold} available."

        score = 0.0
        reasons: List[str] = []
        risks: List[str] = []
        if price:
            reasons.append(f"Affordable shop option at {price} gold.")
            remaining = gold - price
            if remaining < 30:
                score -= 8.0
                risks.append("Buying this leaves very little gold for removal or potions.")
            elif remaining >= 75:
                score += 4.0
                reasons.append("Leaves enough gold for a later purchase.")
        if item_type == "remove":
            starter_density = self._starter_density(state)
            score += 10.0 + starter_density * 18.0
            reasons.append("Removal value scales with starter-card density.")
        elif item_type == "potion":
            if len(state.get("potions", [])) >= 3:
                score -= 35.0
                risks.append("Potion slots appear full, so buying a potion is constrained.")
            if "low_hp" in self.kb.risk_tags(state):
                score += 10.0
                reasons.append("Low HP makes a safety potion more attractive.")
        elif item_type == "relic":
            score += 4.0 if gold >= 180 else -4.0
        return score, " ".join(reasons[:2]), " ".join(risks[:2])

    def _starter_density(self, state: Dict[str, Any]) -> float:
        deck = [str(card).lower() for card in state.get("deck", [])]
        if not deck:
            return 0.0
        starter_names = {
            "strike",
            "defend",
            "neutralize",
            "survivor",
            "bash",
            "zap",
            "dualcast",
            "eruption",
            "vigilance",
        }
        starter_count = sum(1 for card in deck if any(card.startswith(name) for name in starter_names))
        return starter_count / max(1, len(deck))

    def _relic_context_adjustment(
        self,
        option: Dict[str, Any],
        query_type: str,
        state: Dict[str, Any],
        deck_tags: List[str],
        risk_tags: List[str],
        scene_type: str,
    ) -> tuple[float, List[str], List[str], List[Dict[str, Any]]]:
        if option.get("entity_type") != "relic" or query_type not in {"relic_pick", "shop"}:
            return 0.0, [], [], []

        option_id = option.get("id", "")
        score = 0.0
        reasons: List[str] = []
        risks: List[str] = []
        evidence: List[Dict[str, Any]] = []
        is_boss_relic = self._is_boss_relic_context(state, scene_type)
        energy_relics = {
            "coffee_dripper",
            "cursed_key",
            "ectoplasm",
            "fusion_hammer",
            "mark_of_pain",
            "philosophers_stone",
            "runic_dome",
            "slavers_collar",
            "sozu",
            "velvet_choker",
        }
        deck_energy_need = self._deck_needs_energy(state)
        deck_size = len(state.get("deck", []))
        hp_ratio = float(state.get("current_hp", 0) or 0) / max(float(state.get("max_hp", 1) or 1), 1.0)
        starter_density = self._starter_density(state)
        tag_counts = Counter(deck_tags)

        if is_boss_relic:
            if option_id in energy_relics:
                if deck_energy_need:
                    score += 28.0
                    reasons.append("Boss energy relic helps a deck with expensive cards or Act 2+ energy pressure.")
                else:
                    score += 4.0
                    reasons.append("Extra energy is broadly useful, but this deck is not desperate for it.")
            if option_id == "coffee_dripper" and (hp_ratio < 0.55 or "low_hp" in risk_tags):
                score -= 18.0
                risks.append("Coffee Dripper is risky while HP is low because it removes resting.")
            if option_id == "sozu":
                if len(state.get("potions", [])) <= 1 and state.get("act", 1) <= 2:
                    score -= 32.0
                    risks.append("Sozu blocks future potion support, which matters before difficult acts.")
                if not deck_energy_need:
                    score -= 8.0
                    risks.append("Sozu is less attractive when the deck is not under strong energy pressure.")
                else:
                    reasons.append("Sozu downside is smaller when potion support is already less important.")
            if option_id == "ectoplasm" and state.get("act", 1) <= 2:
                score -= 24.0
                risks.append("Ectoplasm blocks future gold, reducing shop and removal flexibility.")
            if option_id == "runic_dome":
                score -= 30.0
                risks.append("Runic Dome hides intents, which is dangerous for real-time advice and high-variance fights.")
            if option_id == "fusion_hammer" and len(state.get("upgraded_cards", [])) < max(2, deck_size // 5):
                score -= 16.0
                risks.append("Fusion Hammer removes upgrades while the deck still has many upgrade targets.")
            if option_id == "busted_crown" and deck_size < 22:
                score -= 28.0
                risks.append("Busted Crown is costly before the deck is mostly complete.")
            if option_id == "velvet_choker" and (tag_counts["draw"] + tag_counts["shiv"] + tag_counts["zero_cost"] >= 3):
                score -= 18.0
                risks.append("Velvet Choker conflicts with draw, shiv, or low-cost multi-card turns.")
            if option_id == "snecko_eye":
                if self._average_card_cost(state) >= 1.45:
                    score += 16.0
                    reasons.append("Snecko Eye fits a higher-cost deck and adds strong draw.")
                else:
                    score -= 26.0
                    risks.append("Snecko Eye is less reliable when the deck is mostly cheap cards.")
            if option_id == "runic_pyramid":
                score += 12.0
                reasons.append("Runic Pyramid improves hand control and lets key cards wait for the right turn.")
                if tag_counts["discard"] >= 2:
                    score += 6.0
                    reasons.append("Existing discard tools help manage Pyramid hand clog.")
            if option_id == "empty_cage" and starter_density >= 0.25:
                score += 18.0
                reasons.append("Empty Cage is strong with many starter cards left to remove.")
            if option_id == "black_star" and self._elite_ready(state, deck_tags, state.get("character_class", "").lower()):
                score += 12.0
                reasons.append("Black Star is better when the deck can safely take elites.")
            if option_id == "tiny_house":
                score -= 22.0
                risks.append("Tiny House is stable but usually lower impact than a focused Boss relic.")
            evidence.append(
                {
                    "type": "boss_relic_rule",
                    "deck_energy_need": deck_energy_need,
                    "hp_ratio": round(hp_ratio, 3),
                    "starter_density": round(starter_density, 3),
                    "source": "internal://skills/boss-relic-rules",
                    "confidence": 0.72,
                }
            )

        if option_id in {"kunai", "shuriken", "ornamental_fan"} and tag_counts["shiv"] + tag_counts["attack_count"] >= 2:
            score += 16.0
            reasons.append("Attack-count relic scales well with shiv or multi-attack decks.")
        if option_id == "thread_and_needle" and ("low_defense" in risk_tags or "low_hp" in risk_tags):
            score += 12.0
            reasons.append("Thread and Needle improves safety immediately.")
        if option_id == "bag_of_preparation" and (tag_counts["draw"] >= 2 or deck_size >= 18):
            score += 10.0
            reasons.append("Opening draw improves consistency for a larger or draw-focused deck.")
        if option_id == "mummified_hand" and tag_counts["power"] >= 2:
            score += 14.0
            reasons.append("Mummified Hand scales strongly with a Power-heavy deck.")
        if option_id in {"snecko_skull", "the_specimen"} and tag_counts["poison"] >= 2:
            score += 15.0
            reasons.append("Poison relic has strong payoff because the deck already applies Poison.")

        return score, reasons[:3], risks[:3], evidence

    def _is_boss_relic_context(self, state: Dict[str, Any], scene_type: str) -> bool:
        current_screen = str(state.get("current_screen") or "").upper()
        return scene_type == "boss_relic" or "BOSS" in current_screen

    def _average_card_cost(self, state: Dict[str, Any]) -> float:
        character_class = state.get("character_class", "").lower()
        costs: List[float] = []
        for card_id in self.kb.resolve_many(state.get("deck", []), character_class):
            card = self.kb.get(card_id, character_class) or {}
            cost = card.get("energy_cost")
            if isinstance(cost, int):
                costs.append(float(max(0, cost)))
            elif cost == "X":
                costs.append(1.5)
        if not costs:
            return 1.0
        return sum(costs) / len(costs)

    def _deck_needs_energy(self, state: Dict[str, Any]) -> bool:
        act = int(state.get("act", 1) or 1)
        energy = int(state.get("energy", 3) or 3)
        avg_cost = self._average_card_cost(state)
        character_class = state.get("character_class", "").lower()
        deck_ids = self.kb.resolve_many(state.get("deck", []), character_class)
        expensive_count = 0
        for card_id in deck_ids:
            card = self.kb.get(card_id, character_class) or {}
            cost = card.get("energy_cost")
            if isinstance(cost, int) and cost >= 2:
                expensive_count += 1
        return energy <= 3 and (act >= 2 or avg_cost >= 1.35 or expensive_count >= 4)

    def _apply_skip_card_context(self, scores: List[Dict[str, Any]], query_type: str, state: Dict[str, Any]) -> None:
        if query_type != "card_pick":
            return
        skip = next((item for item in scores if item.get("option_id") == "skip"), None)
        if not skip:
            return
        deck_size = len(state.get("deck", []))
        act = int(state.get("act", 1) or 1)
        if deck_size < 18 or act < 2:
            return
        non_skip = [item for item in scores if item is not skip and item.get("valid", True)]
        if not non_skip:
            return

        def has_decisive_signal(item: Dict[str, Any]) -> bool:
            if item.get("strategy_signal", 0) > 0:
                return True
            for evidence in item.get("evidence", []) or []:
                if evidence.get("type") in {"archetype_rule", "risk_cover"}:
                    return True
            decisive_phrases = (
                "Fixes an AoE weakness",
                "Improves a low-defense",
                "Adds scaling",
                "Current HP is low",
                "Low-cost consistency",
            )
            return any(any(phrase in reason for phrase in decisive_phrases) for reason in item.get("reasons", []))

        if any(has_decisive_signal(item) for item in non_skip):
            return
        best_other = max(float(item.get("raw_score", item.get("score", 0)) or 0) for item in non_skip)
        promoted = best_other + 2.0
        skip["raw_score"] = round(promoted, 2)
        skip["score"] = self._display_score(promoted)
        skip.setdefault("reasons", []).append("No offered card has a decisive archetype or risk-cover signal, so skipping protects deck quality.")
        skip["confidence"] = max(float(skip.get("confidence", 0.0) or 0.0), 0.62)

    def _display_score(self, raw_score: float) -> float:
        if raw_score <= 100:
            return round(max(0.0, raw_score), 2)
        overflow = raw_score - 100
        return round(min(100.0, 100 - 28 / (1 + overflow / 28)), 2)

    def _score_pathing(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        risk_tags = [] if state.get("_ablation_disable_risk") else self.kb.risk_tags(state)
        deck_tags = self._deck_tags(state)
        hp_ratio = state.get("current_hp", state.get("max_hp", 1)) / max(state.get("max_hp", 1), 1)
        character_class = state.get("character_class", "").lower()
        options = self._pathing_options(state)
        scored = []
        for raw_option in options:
            route = self._parse_route_option(raw_option)
            path = route["path"]
            metadata = route["metadata"]
            if len(path) == 1 and not metadata:
                entity = self.kb.get(path[0], character_class) or {"id": path[0], "name": str(raw_option), "base_value": 45, "tags": []}
                base_name = entity.get("name", route["name"])
                score = float(entity.get("base_value", 45))
            else:
                base_name = route["name"]
                score = 44.0 + len(path) * 2.0

            reasons: List[str] = []
            risks: List[str] = []
            counts = Counter(path)
            forced_elites = int(metadata.get("forced_elites", 0) or 0)
            optional_elites = int(metadata.get("optional_elites", 0) or 0)
            campfires_before_elite = int(metadata.get("campfires_before_elite", 0) or 0)
            shops_before_elite = int(metadata.get("shops_before_elite", 0) or 0)
            if forced_elites:
                counts["elite"] = max(counts["elite"], forced_elites)
            if campfires_before_elite:
                counts["rest"] = max(counts["rest"], campfires_before_elite)
            if shops_before_elite:
                counts["shop"] = max(counts["shop"], shops_before_elite)
            score += counts["treasure"] * 14
            score += counts["rest"] * (18 if "low_hp" in risk_tags else 8)
            score += counts["shop"] * self._shop_path_value(state)
            score += counts["monster"] * self._monster_path_value(state, deck_tags)
            score += counts["event"] * self._event_path_value(state, risk_tags)
            score += counts["unknown"] * self._event_path_value(state, risk_tags)
            score += counts["elite"] * self._elite_path_value(state, risk_tags, deck_tags, character_class)
            score += optional_elites * (10 if self._elite_ready(state, deck_tags, character_class) else 2)

            if counts["elite"]:
                if self._elite_ready(state, deck_tags, character_class):
                    reasons.append("Elite path is justified by current frontload, potions, HP, or a nearby rest site.")
                else:
                    risks.append("Elite path is risky without enough frontload damage, potion support, or HP.")
            if forced_elites:
                risks.append(f"Route contains {forced_elites} forced elite encounter(s).")
            if optional_elites:
                reasons.append("Optional elite branch preserves reward upside without fully locking in risk.")
            if campfires_before_elite and counts["elite"]:
                reasons.append("Campfire before elite gives a recovery or upgrade checkpoint.")
                score += 8
            if shops_before_elite and counts["elite"]:
                reasons.append("Shop before elite can convert gold into potions or frontload.")
                score += 5 if state.get("gold", 0) >= 90 else -2
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
            option_id = route["id"] or self._path_option_id(str(raw_option), path)
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
                            "route_metadata": metadata,
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

    def _pathing_options(self, state: Dict[str, Any]) -> List[Any]:
        options: List[Any] = list(state.get("options") or [])
        existing_keys = {self._route_dedupe_key(option) for option in options}
        for route in state.get("map_options") or []:
            key = self._route_dedupe_key(route)
            if key not in existing_keys:
                options.append(route)
                existing_keys.add(key)
        return options

    def _route_dedupe_key(self, raw_option: Any) -> str:
        if isinstance(raw_option, dict):
            for key in ("id", "route_id", "name", "label"):
                if raw_option.get(key):
                    return str(raw_option[key]).lower()
            nodes = raw_option.get("nodes") or raw_option.get("path") or []
            return "route:" + "|".join(self._normalize_path_node(node) for node in nodes)
        return str(raw_option).lower()

    def _parse_route_option(self, raw_option: Any) -> Dict[str, Any]:
        if not isinstance(raw_option, dict):
            path = self._parse_path_option(str(raw_option))
            return {
                "id": self._path_option_id(str(raw_option), path),
                "name": str(raw_option),
                "path": path,
                "metadata": {},
            }

        nodes = raw_option.get("nodes") or raw_option.get("path") or raw_option.get("route") or raw_option.get("next_nodes") or []
        path = [self._normalize_path_node(node) for node in nodes]
        path = [node for node in path if node]
        if not path:
            for key in ("node_type", "type", "symbol", "name", "label"):
                if raw_option.get(key):
                    path = [self._normalize_path_node(raw_option[key])]
                    break
        if not path:
            path = ["unknown"]

        metadata_keys = {
            "forced_elites",
            "optional_elites",
            "campfires_before_elite",
            "shops_before_elite",
            "monster_count",
            "event_count",
            "rest_count",
            "shop_count",
            "treasure_count",
            "floor",
            "act",
        }
        metadata = {key: raw_option[key] for key in metadata_keys if key in raw_option}
        count_aliases = {
            "monster_count": "monster",
            "event_count": "event",
            "rest_count": "rest",
            "shop_count": "shop",
            "treasure_count": "treasure",
        }
        for source_key, node_type in count_aliases.items():
            for _ in range(max(0, int(metadata.get(source_key, 0) or 0))):
                path.append(node_type)

        option_id = raw_option.get("id") or raw_option.get("route_id") or self._path_option_id(str(raw_option), path)
        name = raw_option.get("name") or raw_option.get("label") or " > ".join(path)
        return {"id": str(option_id), "name": str(name), "path": path, "metadata": metadata}

    def _normalize_path_node(self, node: Any) -> str:
        if isinstance(node, dict):
            for key in ("node_type", "type", "symbol", "name", "label"):
                if node.get(key):
                    return self._parse_path_option(str(node[key]))[0]
            return "unknown"
        return self._parse_path_option(str(node))[0]

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
            if "elite_safety" in option_tags and "low_hp" in risk_tags:
                score += 10
                reasons.append("Low HP makes a safety potion more attractive.")
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

        if query_type == "shop":
            option_id = option.get("id", "")
            gold = state.get("gold", 0)
            deck_size = len(state.get("deck", []))
            if option_id == "remove_card":
                if gold < 75:
                    return -50.0, "", "Gold is too low to rely on card removal.", True
                if deck_size < 10:
                    return -18.0, "", "The deck is still small, so removal is less urgent than adding power.", True
            if option_id == "buy_relic" and gold < 150:
                return -45.0, "", "Gold is below a typical relic-buying threshold.", True
            if option_id == "buy_card" and gold < 50:
                return -35.0, "", "Gold is low, so buying cards is constrained.", True
            if option_id == "buy_potion" and gold < 50:
                return -18.0, "", "Gold is low, so even potion buying is constrained.", True
            if "spend_gold" in option.get("tags", []) and gold < 75:
                return -18.0, "", "Gold is low, so paid shop actions are less attractive.", True
        if query_type == "pathing" and entity_type == "path_node" and option["id"] == "elite":
            if state.get("current_hp", state.get("max_hp", 1)) / max(state.get("max_hp", 1), 1) < 0.45:
                return -18.0, "", "Elite path is dangerous at the current HP total.", True
        return 0.0, "", "", True

    def _skip_card_adjustment(self, option: Dict[str, Any], query_type: str, state: Dict[str, Any]) -> tuple[float, str, str]:
        option_id = option.get("id", "")
        if query_type != "card_pick" or option_id not in {"skip", "skip_card"}:
            return 0.0, "", ""
        deck_size = len(state.get("deck", []))
        act = int(state.get("act", 1) or 1)
        floor = int(state.get("current_floor", 1) or 1)
        risk_tags = set(self.kb.risk_tags(state))
        score = 0.0
        reasons: List[str] = []
        risks: List[str] = []
        if deck_size <= 12 and act == 1 and floor <= 12:
            score -= 18.0
            risks.append("Skipping early can leave the deck short on damage, block, or scaling.")
        if deck_size >= 24:
            score += 16.0
            reasons.append("The deck is already large, so skipping preserves draw consistency.")
        elif deck_size >= 18:
            score += 9.0
            reasons.append("Skipping can be correct when the offered cards do not improve the current plan.")
        if act >= 2:
            score += 7.0
            reasons.append("Later acts punish low-impact additions more, so skip is a real option.")
        if risk_tags.intersection({"no_aoe", "low_defense", "slow_scaling"}):
            score -= 7.0
            risks.append("The deck still has unresolved structural risks, so skipping needs a weak reward screen.")
        if not reasons:
            reasons.append("Skip avoids adding a low-impact card that dilutes future draws.")
        return score, " ".join(reasons), " ".join(risks)

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
