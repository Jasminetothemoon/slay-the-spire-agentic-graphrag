import argparse
import json
from pathlib import Path
from typing import Any, Dict


PUBLIC_FACT_COLLECTIONS = {"cards", "relics", "potions", "enemies"}
SYSTEM_COLLECTIONS = {"classes", "shop_actions", "path_nodes"}
DERIVED_COLLECTIONS = {"mechanics"}
ALL_COLLECTIONS = [
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


def present(value: Any) -> bool:
    return value not in (None, "", [], {})


def entity_source_defaults(collection: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    patch_version = metadata.get("patch_version", "unknown")
    if collection in PUBLIC_FACT_COLLECTIONS:
        return {
            "source": metadata.get("source", "unknown"),
            "source_url": metadata.get("source_url", ""),
            "confidence": metadata.get("confidence", 0.7),
            "patch_version": patch_version,
        }
    if collection in SYSTEM_COLLECTIONS:
        return {
            "source": "system",
            "source_url": "internal://system-support-entity",
            "confidence": 1.0,
            "patch_version": patch_version,
        }
    if collection in DERIVED_COLLECTIONS:
        return {
            "source": "derived",
            "source_url": "internal://mechanic-extraction",
            "confidence": 0.7,
            "patch_version": patch_version,
        }
    return {
        "source": "curated",
        "source_url": "internal://curated-strategy",
        "confidence": 0.6,
        "patch_version": patch_version,
    }


def normalize_entity(entity: Dict[str, Any], collection: str, metadata: Dict[str, Any]) -> None:
    defaults = entity_source_defaults(collection, metadata)
    for field, value in defaults.items():
        if not present(entity.get(field)):
            entity[field] = value


def normalize_relationship(entity: Dict[str, Any], collection: str) -> None:
    for relationship in entity.get("relationships", []):
        if not present(relationship.get("source")):
            relationship["source"] = "derived_relationship"
        if not present(relationship.get("source_url")):
            relationship["source_url"] = f"internal://relationship-extraction/{collection}/{entity.get('id', 'unknown')}"
        if not present(relationship.get("confidence")):
            relationship["confidence"] = min(float(entity.get("confidence", 0.6)), 0.75)


def normalize(data: Dict[str, Any]) -> Dict[str, Any]:
    metadata = data.setdefault("metadata", {})
    metadata.setdefault("provenance_normalized", True)
    for collection in ALL_COLLECTIONS:
        for entity in data.get(collection, []):
            normalize_entity(entity, collection, metadata)
            normalize_relationship(entity, collection)
    metadata["provenance_normalized"] = True
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Add consistent provenance fields to a knowledge dataset.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(Path(args.input), "r", encoding="utf-8") as f:
        data = json.load(f)

    data = normalize(data)

    with open(Path(args.output), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(json.dumps(data.get("metadata", {}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
