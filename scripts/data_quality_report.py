import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


COLLECTIONS = ["cards", "relics", "potions", "enemies", "archetypes", "shop_actions", "path_nodes"]


def missing_count(items: List[Dict[str, Any]], field: str) -> int:
    return sum(1 for item in items if item.get(field) in (None, "", []))


def average_relationships(items: List[Dict[str, Any]]) -> float:
    if not items:
        return 0.0
    return round(sum(len(item.get("relationships", [])) for item in items) / len(items), 2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Report coverage and field quality for a knowledge dataset.")
    parser.add_argument("--data", required=True)
    args = parser.parse_args()

    with open(Path(args.data), "r", encoding="utf-8") as f:
        data = json.load(f)

    report = {
        "metadata": data.get("metadata", {}),
        "collections": {},
    }
    for collection in COLLECTIONS:
        items = data.get(collection, [])
        report["collections"][collection] = {
            "count": len(items),
            "missing_description": missing_count(items, "description"),
            "missing_tags": missing_count(items, "tags"),
            "avg_relationships": average_relationships(items),
        }
        if collection == "cards":
            report["collections"][collection].update(
                {
                    "missing_type": missing_count(items, "type"),
                    "missing_energy_cost": missing_count(items, "energy_cost"),
                }
            )

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
