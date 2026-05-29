import json
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.main import ModStatePayload, build_recommendation_response, normalize_mod_state
from sts_engine.knowledge_base import load_knowledge_base
from sts_engine.localization import localize_response, localize_state


LOCALIZATION_PATH = ROOT / "data" / "localization_zhs.json"


def expect(errors: List[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def check_snapshot(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    expected_names = {
        "strike_watcher": "打击",
        "defend_watcher": "防御",
        "eruption": "暴怒",
        "vigilance": "警惕",
        "pure_water": "至纯之水",
        "halt": "停顿",
        "just_lucky": "幸运一击",
        "consecrate": "供奉",
    }
    entities = data.get("entities", {})
    for entity_id, expected_name in expected_names.items():
        actual = entities.get(entity_id, {}).get("name")
        expect(errors, actual == expected_name, f"{entity_id}: expected {expected_name}, got {actual}")
    expect(errors, data.get("metadata", {}).get("entity_count", 0) >= 550, "Chinese snapshot should cover 550+ entities.")
    return errors


def check_resolution() -> List[str]:
    kb = load_knowledge_base()
    expected = {
        ("打击", "watcher"): "strike_watcher",
        ("防御", "watcher"): "defend_watcher",
        ("暴怒", "watcher"): "eruption",
        ("幸运一击", "watcher"): "just_lucky",
        ("至纯之水", "watcher"): "pure_water",
    }
    errors: List[str] = []
    for (name, character_class), expected_id in expected.items():
        actual = kb.resolve_id(name, character_class)
        expect(errors, actual == expected_id, f"Chinese alias {name}: expected {expected_id}, got {actual}")
    return errors


def check_state_localization() -> List[str]:
    state = normalize_mod_state(
        ModStatePayload(
            run_id="localization_check",
            character_class="watcher",
            deck=["Strike_P", "Eruption", "Vigilance"],
            relics=["PureWater"],
        )
    )
    localized = state.get("localized", {}).get("zh", {})
    errors: List[str] = []
    expect(errors, localized.get("character_class") == "观者", "State class should localize to 观者.")
    expect(errors, localized.get("deck") == ["打击", "暴怒", "警惕"], f"State deck should localize, got {localized.get('deck')}")
    expect(errors, localized.get("relics") == ["至纯之水"], f"State relics should localize, got {localized.get('relics')}")
    manual = localize_state({"character_class": "watcher", "deck": ["just_lucky"], "relics": ["pure_water"]})
    expect(errors, manual.get("deck") == ["幸运一击"], f"Manual state should localize card names, got {manual}")
    return errors


def check_recommendation_localization() -> List[str]:
    response = build_recommendation_response(
        {
            "run_id": "localization_recommendation",
            "character_class": "watcher",
            "query_type": "card_pick",
            "deck": ["strike_watcher", "eruption", "vigilance"],
            "relics": ["pure_water"],
            "potions": [],
            "options": ["halt", "just_lucky", "consecrate"],
        }
    ).model_dump()
    localized = response.get("localized", {}).get("zh", {})
    scores = localized.get("option_scores", [])
    errors: List[str] = []
    expect(errors, bool(scores), "Localized recommendation should include option_scores.")
    names = {score.get("name") for score in scores}
    expect(errors, {"停顿", "幸运一击", "供奉"}.issubset(names), f"Localized option names are incomplete: {names}")
    expect(errors, "Recommended:" not in localized.get("reasoning", ""), "Reasoning should not remain in English template form.")
    expect(errors, "推荐" in localized.get("reasoning", ""), f"Reasoning should be Chinese, got {localized.get('reasoning')}")

    direct = localize_response(
        {
            "recommendation": "just_lucky",
            "reasoning": "Recommended: Just Lucky (score 60.0, confidence 0.80).",
            "option_scores": [{"option_id": "just_lucky", "name": "Just Lucky", "reasons": ["Matches the current character card pool."], "risks": []}],
            "risk_report": {"risks": ["no_aoe"], "summary": "Detected: missing AoE.", "deck_tags": ["frontload_damage"]},
        }
    )
    expect(errors, direct.get("recommendation_name") == "幸运一击", "Direct localized response should translate recommendation name.")
    expect(errors, direct.get("risk_report", {}).get("risks") == ["缺少群体伤害"], "Risk labels should be Chinese.")
    return errors


def main() -> None:
    if not LOCALIZATION_PATH.exists():
        raise SystemExit(f"Missing localization snapshot: {LOCALIZATION_PATH}")
    data = json.loads(LOCALIZATION_PATH.read_text(encoding="utf-8"))
    load_knowledge_base.cache_clear()
    errors: List[str] = []
    errors.extend(check_snapshot(data))
    errors.extend(check_resolution())
    errors.extend(check_state_localization())
    errors.extend(check_recommendation_localization())
    if errors:
        raise SystemExit("\n".join(errors))
    print("Localization checks passed: Chinese names, state localization, recommendation localization, alias resolution")


if __name__ == "__main__":
    main()
