import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA_PATH = ROOT / "data" / "sample_data.json"


COLLECTIONS = [
    "classes",
    "mechanics",
    "cards",
    "relics",
    "potions",
    "enemies",
    "archetypes",
    "shop_actions",
    "path_nodes",
]


def main() -> None:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    ids = set()
    errors = []
    for collection in COLLECTIONS:
        for entity in data.get(collection, []):
            entity_id = entity.get("id")
            if not entity_id:
                errors.append(f"{collection}: missing id")
                continue
            if entity_id in ids:
                errors.append(f"duplicate id: {entity_id}")
            ids.add(entity_id)
            if "name" not in entity:
                errors.append(f"{entity_id}: missing name")

    for collection in COLLECTIONS:
        for entity in data.get(collection, []):
            for rel in entity.get("relationships", []):
                if rel.get("target") not in ids:
                    errors.append(f"{entity['id']}: missing relationship target {rel.get('target')}")
                if rel.get("type") not in {
                    "APPLIES",
                    "SCALES_WITH",
                    "ENHANCES",
                    "COUNTERS",
                    "CORE_PIECE_FOR",
                    "PUNISHES",
                    "GOOD_AGAINST",
                    "RISKY_WHEN",
                }:
                    errors.append(f"{entity['id']}: unsupported relationship type {rel.get('type')}")

    if errors:
        raise SystemExit("\n".join(errors))

    print("Data validation passed.")
    for collection in COLLECTIONS:
        print(f"{collection}: {len(data.get(collection, []))}")


if __name__ == "__main__":
    main()
