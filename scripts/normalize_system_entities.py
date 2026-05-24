import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


SHOP_ACTIONS = [
    {"id": "remove_card", "name": "Remove a Card", "base_value": 68, "tags": ["deck_control"]},
    {"id": "buy_card", "name": "Buy Card", "base_value": 56, "tags": ["deck_growth", "spend_gold"]},
    {"id": "buy_relic", "name": "Buy Relic", "base_value": 64, "tags": ["power_spike", "spend_gold"]},
    {"id": "buy_potion", "name": "Buy Potion", "base_value": 48, "tags": ["elite_safety", "spend_gold"]},
    {"id": "skip_shop", "name": "Skip", "base_value": 25, "tags": ["save_gold"]},
]

PATH_NODES = [
    {"id": "monster", "name": "Monster", "base_value": 42, "tags": ["card_reward"]},
    {"id": "elite", "name": "Elite", "base_value": 62, "tags": ["reward", "risk"]},
    {"id": "rest", "name": "Rest Site", "base_value": 54, "tags": ["heal", "upgrade"]},
    {"id": "shop", "name": "Shop", "base_value": 52, "tags": ["spend_gold"]},
    {"id": "event", "name": "Event", "base_value": 46, "tags": ["variance", "event"]},
    {"id": "treasure", "name": "Treasure", "base_value": 58, "tags": ["relic_reward"]},
    {"id": "unknown", "name": "Unknown", "base_value": 45, "tags": ["variance"]},
]

STARTER_CARD_ALIASES = [
    {
        "id": "strike_ironclad",
        "name": "Strike",
        "class": "ironclad",
        "source_id": "strike_defect",
        "description": "Starter attack card. Deal 6(9) damage.",
    },
    {
        "id": "defend_ironclad",
        "name": "Defend",
        "class": "ironclad",
        "source_id": "defend_defect",
        "description": "Starter skill card. Gain 5(8) Block.",
    },
    {
        "id": "strike_silent",
        "name": "Strike",
        "class": "silent",
        "source_id": "strike_defect",
        "description": "Starter attack card. Deal 6(9) damage.",
    },
    {
        "id": "defend_silent",
        "name": "Defend",
        "class": "silent",
        "source_id": "defend_defect",
        "description": "Starter skill card. Gain 5(8) Block.",
    },
    {
        "id": "strike_watcher",
        "name": "Strike",
        "class": "watcher",
        "source_id": "strike_defect",
        "description": "Starter attack card. Deal 6(9) damage.",
    },
    {
        "id": "defend_watcher",
        "name": "Defend",
        "class": "watcher",
        "source_id": "defend_defect",
        "description": "Starter skill card. Gain 5(8) Block.",
    },
]


def merge_by_id(existing: List[Dict[str, Any]], required: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_id = {item["id"]: item for item in existing}
    for item in required:
        current = by_id.get(item["id"], {})
        merged = dict(item)
        merged.update(current)
        if not current.get("tags"):
            merged["tags"] = item["tags"]
        by_id[item["id"]] = merged
    order = {item["id"]: index for index, item in enumerate(required)}
    return sorted(by_id.values(), key=lambda item: (order.get(item["id"], 999), item.get("name", "")))


def ensure_starter_aliases(cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_id = {item["id"]: item for item in cards}
    normalized = list(cards)
    for alias in STARTER_CARD_ALIASES:
        if alias["id"] in by_id:
            continue
        source = by_id.get(alias["source_id"])
        if not source:
            continue
        card = dict(source)
        card.update(
            {
                "id": alias["id"],
                "name": alias["name"],
                "class": alias["class"],
                "source": "system",
                "source_url": f"internal://system-support-entity/cards/{alias['id']}",
                "confidence": 1.0,
                "description": alias["description"],
            }
        )
        card["relationships"] = [
            {
                **relationship,
                "source": "system",
                "source_url": f"internal://system-support-entity/cards/{alias['id']}",
                "confidence": 1.0,
            }
            for relationship in source.get("relationships", [])
        ]
        by_id[alias["id"]] = card
        normalized.append(card)
    return normalized


def normalize(data: Dict[str, Any]) -> Dict[str, Any]:
    data["cards"] = ensure_starter_aliases(data.get("cards", []))
    data["shop_actions"] = merge_by_id(data.get("shop_actions", []), SHOP_ACTIONS)
    data["path_nodes"] = merge_by_id(data.get("path_nodes", []), PATH_NODES)
    data.setdefault("metadata", {})["entity_counts"] = {
        key: len(data.get(key, []))
        for key in ("classes", "mechanics", "cards", "relics", "potions", "enemies", "archetypes", "shop_actions", "path_nodes")
    }
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Ensure required system support entities exist in a knowledge dataset.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(Path(args.input), "r", encoding="utf-8") as f:
        data = json.load(f)

    data = normalize(data)

    with open(Path(args.output), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(json.dumps(data["metadata"]["entity_counts"], indent=2))


if __name__ == "__main__":
    main()
