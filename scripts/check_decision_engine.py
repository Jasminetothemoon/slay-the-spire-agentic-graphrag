import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sts_engine.agent import build_graph
from sts_engine.knowledge_base import load_knowledge_base
from scripts.communication_mod_adapter import read_json, run_offline


DEFAULT_DATA = ROOT / "data" / "public_full_data.json"


def check_class_aware_resolution(kb: Any) -> List[str]:
    expected = {
        ("Strike", "ironclad"): "strike_ironclad",
        ("Defend", "ironclad"): "defend_ironclad",
        ("Strike", "silent"): "strike_silent",
        ("Defend", "silent"): "defend_silent",
        ("Strike", "defect"): "strike_defect",
        ("Defend", "defect"): "defend_defect",
        ("Strike", "watcher"): "strike_watcher",
        ("Defend", "watcher"): "defend_watcher",
    }
    errors = []
    for (card_name, character_class), expected_id in expected.items():
        actual = kb.resolve_id(card_name, character_class)
        if actual != expected_id:
            errors.append(f"{character_class} {card_name}: expected {expected_id}, got {actual}")
    return errors


def check_legality_filter() -> List[str]:
    engine = build_graph()
    state: Dict[str, Any] = {
        "run_id": "decision_engine_check",
        "character_class": "silent",
        "query_type": "card_pick",
        "deck": ["Strike", "Defend"],
        "relics": [],
        "potions": [],
        "options": ["Dagger Spray", "Burning Blood", "Elite"],
    }
    result = engine.invoke(state)
    by_id = {item["option_id"]: item for item in result.get("option_scores", [])}
    errors = []
    if by_id.get("dagger_spray", {}).get("valid") is not True:
        errors.append("Dagger Spray should be a valid card_pick option.")
    for option_id in ("burning_blood", "elite"):
        if by_id.get(option_id, {}).get("valid") is not False:
            errors.append(f"{option_id} should be invalid for card_pick.")
    evidence = by_id.get("dagger_spray", {}).get("evidence", [])
    if not any(item.get("owned_id") == "strike_silent" for item in evidence):
        errors.append("Silent starter Strike should resolve to strike_silent in graph evidence.")
    panel = result.get("explanation_panel", {})
    if not panel.get("why_pick") or not panel.get("candidate_comparison"):
        errors.append("Recommendation should include a structured explanation_panel.")
    return errors


def check_communication_mod_adapter() -> List[str]:
    sample = read_json(ROOT / "data" / "communication_mod_sample_state.json")
    result = run_offline(sample, recommend=True)
    state = result["state"]
    recommendation = result.get("recommendation", {})
    errors = []
    if state.get("character_class") != "silent":
        errors.append(f"CommunicationMod class should normalize to silent, got {state.get('character_class')}")
    if result.get("recommendation_request", {}).get("query_type") != "card_pick":
        errors.append("CARD_REWARD screen should infer card_pick query_type.")
    if recommendation.get("recommendation") not in {"catalyst", "corpse_explosion"}:
        errors.append(
            "Sample CommunicationMod recommendation should be a strong poison/AoE payoff, "
            f"got {recommendation.get('recommendation')}"
        )
    if not recommendation.get("option_scores"):
        errors.append("CommunicationMod offline recommendation should include option_scores.")
    return errors


def check_combat_advice() -> List[str]:
    engine = build_graph()
    state: Dict[str, Any] = {
        "run_id": "combat_check",
        "character_class": "silent",
        "query_type": "combat",
        "energy": 3,
        "deck": ["Strike", "Defend", "Neutralize", "Survivor", "Dagger Spray"],
        "relics": [],
        "potions": ["Block Potion"],
        "hand_cards": ["Neutralize", "Survivor", "Strike", "Dagger Spray", "Defend"],
        "enemies": [
            {"name": "Blue Slaver", "hp": 13, "intent": "attack", "intent_damage": 12},
            {"name": "Red Slaver", "hp": 33, "intent": "attack", "intent_damage": 8},
        ],
        "combat_state": {"incoming_damage": 20},
    }
    result = engine.invoke(state)
    scores = result.get("option_scores", [])
    errors = []
    if not scores:
        errors.append("Combat query should return play sequence scores.")
        return errors
    top = scores[0]
    if top.get("decision_type") != "combat":
        errors.append("Combat top score should be tagged with decision_type=combat.")
    if "->" not in top.get("name", "") and not top.get("name", "").startswith("Use "):
        errors.append(f"Combat top score should name a play sequence or potion use, got {top.get('name')}")
    if not top.get("evidence") or top["evidence"][0].get("type") not in {"combat_estimate", "combat_potion"}:
        errors.append("Combat top score should include combat evidence.")
    return errors


def check_pathing_route_objects() -> List[str]:
    engine = build_graph()
    state: Dict[str, Any] = {
        "run_id": "route_object_check",
        "character_class": "silent",
        "query_type": "pathing",
        "act": 1,
        "current_floor": 12,
        "current_hp": 17,
        "max_hp": 70,
        "gold": 95,
        "deck": ["Strike", "Defend", "Backflip"],
        "relics": [],
        "potions": [],
        "options": [],
        "map_options": [
            {
                "id": "forced_elite_no_rest",
                "name": "Forced Elite",
                "nodes": ["monster", "elite", "monster"],
                "forced_elites": 1,
                "campfires_before_elite": 0,
            },
            {
                "id": "safe_rest_route",
                "name": "Rest Route",
                "nodes": ["monster", "rest", "treasure"],
                "forced_elites": 0,
                "campfires_before_elite": 1,
            },
        ],
    }
    result = engine.invoke(state)
    scores = result.get("option_scores", [])
    errors = []
    if not scores:
        errors.append("Pathing with map_options should return route scores even when options is empty.")
        return errors
    if scores[0].get("option_id") != "safe_rest_route":
        errors.append(f"Low HP route object should prefer safe_rest_route, got {scores[0].get('option_id')}")
    evidence = scores[0].get("evidence", [{}])[0]
    if evidence.get("type") != "pathing_rule" or "route_metadata" not in evidence:
        errors.append("Route object score should preserve pathing_rule evidence and route_metadata.")
    panel = result.get("explanation_panel", {})
    if not panel.get("candidate_comparison", [{}])[0].get("why_not"):
        errors.append("Candidate comparison should include why_not tradeoff text.")
    return errors


def check_live_mod_normalization() -> List[str]:
    from api.main import ModStatePayload, normalize_mod_state, normalize_option_list

    payload = ModStatePayload(
        run_id="mod_live_check",
        character_class="watcher",
        deck=["æ\u0089\u0093å\u0087»", "æ\u009a´æ\u0080\u0092", "è\u00ad¦æ\u0083\u0095", "å\u008f\u0091æ³\u0084"],
        relics=["è\u0087³çº¯ä¹\u008bæ°´"],
        potions=["è\u008d¯æ°´æ\xa0\u008f"],
    )
    state = normalize_mod_state(payload)
    errors = []
    for expected in ("strike_watcher", "eruption", "vigilance", "tantrum"):
        if expected not in state.get("deck", []):
            errors.append(f"Live Mod normalization should include {expected}, got {state.get('deck')}")
    if state.get("relics") != ["pure_water"]:
        errors.append(f"Live Mod relic should normalize to pure_water, got {state.get('relics')}")
    if state.get("potions") != []:
        errors.append(f"Potion slots should be dropped, got {state.get('potions')}")
    options = normalize_option_list(["Halt", "PureWater", "Remove a Card"], "watcher")
    if options[:2] != ["halt", "pure_water"]:
        errors.append(f"Live Mod options should normalize game ids/names, got {options}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Check decision-engine invariants needed for live Mod state ingestion.")
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    os.environ["STS_KB_PATH"] = str(Path(args.data))
    load_knowledge_base.cache_clear()
    kb = load_knowledge_base(str(Path(args.data)))
    errors = []
    errors.extend(check_class_aware_resolution(kb))
    errors.extend(check_legality_filter())
    errors.extend(check_communication_mod_adapter())
    errors.extend(check_combat_advice())
    errors.extend(check_pathing_route_objects())
    errors.extend(check_live_mod_normalization())
    if errors:
        raise SystemExit("\n".join(errors))
    report = {
        "checks": [
            "class_aware_resolution",
            "decision_legality_filter",
            "communication_mod_adapter",
            "combat_advice",
            "pathing_route_objects",
            "live_mod_normalization",
        ],
        "status": "passed",
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(
            "Decision engine checks passed: class-aware resolution, decision legality filter, "
            "CommunicationMod adapter, combat advice"
        )


if __name__ == "__main__":
    main()
