import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def dedupe_entities(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    normalized = []
    for entity in entities:
        entity = dict(entity)
        entity_id = entity["id"]
        if entity_id in seen:
            continue
        seen.add(entity_id)
        normalized.append(entity)
    return normalized


def normalize(data: Dict[str, Any]) -> Dict[str, Any]:
    collections = ("classes", "mechanics", "cards", "relics", "potions", "enemies", "archetypes", "shop_actions", "path_nodes")
    reserved = set()
    for collection in ("classes", "mechanics"):
        data[collection] = dedupe_entities(data.get(collection, []))
        reserved.update(entity["id"] for entity in data[collection])

    for collection in ("cards", "relics", "potions", "enemies", "archetypes", "shop_actions", "path_nodes"):
        for entity in data.get(collection, []):
            if entity["id"] in reserved:
                old_id = entity["id"]
                entity["id"] = f"{old_id}_{collection[:-1]}"
                _rewrite_relationship_targets(data, old_id, entity["id"], collection)
        data[collection] = dedupe_entities(data.get(collection, []))
        reserved.update(entity["id"] for entity in data[collection])

    data.setdefault("metadata", {})["entity_counts"] = {
        collection: len(data.get(collection, []))
        for collection in collections
    }
    data["metadata"]["normalized"] = True
    return data


def _rewrite_relationship_targets(data: Dict[str, Any], old_id: str, new_id: str, owner_collection: str) -> None:
    # Entity id rewrites should not steal mechanic relationships. Only rewrite
    # references inside the same collection when a duplicate entity id is renamed.
    for entity in data.get(owner_collection, []):
        for relationship in entity.get("relationships", []):
            if relationship.get("target") == old_id:
                relationship["target"] = new_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize imported datasets by removing duplicate entity ids.")
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
