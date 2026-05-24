import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_STATE_PATH = Path("data") / "communication_mod_sample_state.json"

CLASS_MAP = {
    "IRONCLAD": "ironclad",
    "THE_SILENT": "silent",
    "SILENT": "silent",
    "DEFECT": "defect",
    "WATCHER": "watcher",
}

SCREEN_QUERY_MAP = {
    "CARD_REWARD": "card_pick",
    "GRID": "card_pick",
    "SHOP_SCREEN": "shop",
    "SHOP": "shop",
    "BOSS_REWARD": "relic_pick",
    "MAP": "pathing",
    "COMBAT": "combat",
}


def read_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def as_names(items: Optional[Iterable[Any]]) -> List[str]:
    names: List[str] = []
    for item in items or []:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            names.append(str(item.get("name") or item.get("id") or item.get("card_id") or "").strip())
    return [name for name in names if name]


def normalize_class(value: Any) -> str:
    raw = str(value or "silent").strip()
    return CLASS_MAP.get(raw.upper(), raw.lower())


def normalize_state(raw: Dict[str, Any]) -> Dict[str, Any]:
    combat_state = raw.get("combat_state") or {}
    enemies = raw.get("enemies") or raw.get("monsters") or []
    return {
        "run_id": raw.get("run_id") or raw.get("seed") or "communication_mod_live",
        "source": "communication_mod",
        "character_class": normalize_class(raw.get("character_class") or raw.get("class")),
        "ascension_level": int(raw.get("ascension_level") or raw.get("ascension") or 0),
        "act": int(raw.get("act") or 1),
        "current_floor": int(raw.get("current_floor") or raw.get("floor") or 1),
        "current_hp": int(raw.get("current_hp") or raw.get("hp") or 70),
        "max_hp": int(raw.get("max_hp") or raw.get("maxhp") or 70),
        "gold": int(raw.get("gold") or 0),
        "energy": int(raw.get("energy") or raw.get("current_energy") or 3),
        "deck": as_names(raw.get("deck") or raw.get("master_deck")),
        "upgraded_cards": as_names(raw.get("upgraded_cards")),
        "relics": as_names(raw.get("relics")),
        "potions": as_names(raw.get("potions")),
        "combat_state": combat_state,
        "enemies": enemies if isinstance(enemies, list) else [],
        "hand_cards": as_names(raw.get("hand_cards") or raw.get("hand")),
        "draw_pile": as_names(raw.get("draw_pile")),
        "discard_pile": as_names(raw.get("discard_pile")),
        "map_options": raw.get("map_options") or raw.get("next_nodes") or [],
        "boss": raw.get("boss"),
    }


def infer_query_type(raw: Dict[str, Any]) -> str:
    explicit = raw.get("query_type")
    if explicit:
        return str(explicit)
    screen_type = str(raw.get("screen_type") or raw.get("screen") or "").upper()
    return SCREEN_QUERY_MAP.get(screen_type, "card_pick")


def infer_options(raw: Dict[str, Any], query_type: str) -> List[str]:
    for key in ("options", "choice_list", "choices", "cards", "relic_choices", "shop_items"):
        options = as_names(raw.get(key))
        if options:
            return options
    if query_type == "pathing":
        return as_names(raw.get("map_options")) or ["Elite", "Rest Site", "Shop"]
    if query_type == "shop":
        return ["Remove a Card", "Buy Potion", "Skip"]
    return []


def post_json(base_url: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    import requests

    response = requests.post(f"{base_url.rstrip('/')}{path}", json=payload, timeout=15)
    response.raise_for_status()
    return response.json()


def run_once(raw: Dict[str, Any], base_url: str, recommend: bool) -> Dict[str, Any]:
    state = normalize_state(raw)
    state_response = post_json(base_url, "/mod/state", state)
    result: Dict[str, Any] = {"state": state_response}
    if recommend:
        query_type = infer_query_type(raw)
        recommendation_request = {
            "run_id": state_response["run_id"],
            "query_type": query_type,
            "options": infer_options(raw, query_type),
            "user_query": raw.get("user_query") or f"CommunicationMod {query_type} decision.",
        }
        result["recommendation_request"] = recommendation_request
        result["recommendation"] = post_json(base_url, "/get_recommendation", recommendation_request)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Adapt a CommunicationMod-style state JSON into the local recommender API.")
    parser.add_argument("--state-file", default=str(DEFAULT_STATE_PATH), help="Path to a CommunicationMod-style state JSON file.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Local FastAPI base URL.")
    parser.add_argument("--no-recommend", action="store_true", help="Only post /mod/state; do not request a recommendation.")
    args = parser.parse_args()

    raw = read_json(Path(args.state_file))
    result = run_once(raw, args.base_url, recommend=not args.no_recommend)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
