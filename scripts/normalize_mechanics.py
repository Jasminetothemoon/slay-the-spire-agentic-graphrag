import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


REQUIRED_MECHANICS = [
    {"id": "no_aoe", "name": "No AoE", "tags": ["risk", "deck_gap"]},
    {"id": "low_defense", "name": "Low Defense", "tags": ["risk", "deck_gap"]},
    {"id": "low_hp", "name": "Low HP", "tags": ["risk", "run_state"]},
    {"id": "shop_ready", "name": "Shop Ready", "tags": ["run_state", "economy"]},
    {"id": "scaling_damage", "name": "Scaling Damage", "tags": ["damage", "scaling"]},
    {"id": "frontload_block", "name": "Frontload Block", "tags": ["defense", "frontload"]},
    {"id": "deck_control", "name": "Deck Control", "tags": ["consistency"]},
    {"id": "card_removal", "name": "Card Removal", "tags": ["consistency", "shop"]},
    {"id": "artifact_strip", "name": "Artifact Strip", "tags": ["debuff_support"]},
    {"id": "stance_exit", "name": "Stance Exit", "tags": ["watcher", "risk_control"]},
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
    return sorted(by_id.values(), key=lambda item: item["id"])


def normalize(data: Dict[str, Any]) -> Dict[str, Any]:
    data["mechanics"] = merge_by_id(data.get("mechanics", []), REQUIRED_MECHANICS)
    data.setdefault("metadata", {})["entity_counts"] = {
        key: len(data.get(key, []))
        for key in ("classes", "mechanics", "cards", "relics", "potions", "enemies", "archetypes", "shop_actions", "path_nodes")
    }
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Ensure derived mechanics required by scoring and Mod decisions exist.")
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
