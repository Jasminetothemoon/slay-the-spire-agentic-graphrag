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
    if errors:
        raise SystemExit("\n".join(errors))
    report = {
        "checks": ["class_aware_resolution", "decision_legality_filter", "communication_mod_adapter", "combat_advice"],
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
