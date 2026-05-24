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
    if errors:
        raise SystemExit("\n".join(errors))
    report = {
        "checks": ["class_aware_resolution", "decision_legality_filter", "communication_mod_adapter"],
        "status": "passed",
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("Decision engine checks passed: class-aware resolution, decision legality filter, CommunicationMod adapter")


if __name__ == "__main__":
    main()
