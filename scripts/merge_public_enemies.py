import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def merge_enemies(base: Dict[str, Any], supplement: Dict[str, Any]) -> Dict[str, Any]:
    existing = {enemy["id"]: enemy for enemy in base.get("enemies", [])}
    for enemy in supplement.get("enemies", []):
        existing[enemy["id"]] = enemy
    merged: List[Dict[str, Any]] = sorted(existing.values(), key=lambda item: (item.get("type", ""), item.get("name", "")))
    base["enemies"] = merged
    base.setdefault("metadata", {})["entity_counts"] = {
        key: len(base.get(key, []))
        for key in ("classes", "mechanics", "cards", "relics", "potions", "enemies", "archetypes", "shop_actions", "path_nodes")
    }
    return base


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge enemy entities from a supplemental public import into the main dataset.")
    parser.add_argument("--base", required=True)
    parser.add_argument("--supplement", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    base = load_json(Path(args.base))
    supplement = load_json(Path(args.supplement))
    merged = merge_enemies(base, supplement)

    with open(Path(args.output), "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(json.dumps(merged["metadata"]["entity_counts"], indent=2))


if __name__ == "__main__":
    main()
