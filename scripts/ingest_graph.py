import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DEFAULT_DATA = ROOT / "data" / "sample_data.json"


LABELS = {
    "classes": "Class",
    "mechanics": "Mechanic",
    "cards": "Card",
    "relics": "Relic",
    "potions": "Potion",
    "enemies": "Enemy",
    "archetypes": "Archetype",
    "shop_actions": "ShopAction",
    "path_nodes": "PathNode",
}


class GraphIngestor:
    def __init__(self, uri: str, user: str, password: str):
        from neo4j import GraphDatabase

        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        self.driver.close()

    def create_constraints(self) -> None:
        with self.driver.session() as session:
            for label in LABELS.values():
                session.run(f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE")

    def ingest(self, data: Dict[str, Any]) -> None:
        metadata = data.get("metadata", {})
        with self.driver.session() as session:
            for collection, label in LABELS.items():
                for entity in data.get(collection, []):
                    props = self._serializable_props(entity, metadata)
                    session.run(
                        f"""
                        MERGE (n:{label} {{id: $id}})
                        SET n += $props
                        """,
                        id=entity["id"],
                        props=props,
                    )

            for collection, label in LABELS.items():
                for entity in data.get(collection, []):
                    for relationship in entity.get("relationships", []):
                        rel_type = relationship["type"]
                        session.run(
                            f"""
                            MATCH (source:{label} {{id: $source_id}})
                            MATCH (target {{id: $target_id}})
                            MERGE (source)-[r:{rel_type}]->(target)
                            SET r.weight = $weight, r.source = $source
                            """,
                            source_id=entity["id"],
                            target_id=relationship["target"],
                            weight=float(relationship.get("weight", 0.5)),
                            source=metadata.get("source", "unknown"),
                        )

            self._ingest_archetype_members(session, data)

    def _ingest_archetype_members(self, session: Any, data: Dict[str, Any]) -> None:
        for archetype in data.get("archetypes", []):
            for card_id in archetype.get("core_cards", []):
                session.run(
                    """
                    MATCH (c:Card {id: $card_id})
                    MATCH (a:Archetype {id: $archetype_id})
                    MERGE (c)-[:CORE_PIECE_FOR {weight: 1.0}]->(a)
                    """,
                    card_id=card_id,
                    archetype_id=archetype["id"],
                )
            for relic_id in archetype.get("core_relics", []):
                session.run(
                    """
                    MATCH (r:Relic {id: $relic_id})
                    MATCH (a:Archetype {id: $archetype_id})
                    MERGE (r)-[:CORE_PIECE_FOR {weight: 1.0}]->(a)
                    """,
                    relic_id=relic_id,
                    archetype_id=archetype["id"],
                )

    def _serializable_props(self, entity: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        props = {}
        for key, value in entity.items():
            if key == "relationships":
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                props[key] = value
            else:
                props[key] = json.dumps(value, ensure_ascii=False)
        props["game"] = metadata.get("game", "sts1")
        props["patch_version"] = metadata.get("patch_version", "unknown")
        props["source"] = metadata.get("source", "unknown")
        props["confidence"] = float(metadata.get("confidence", 0.5))
        return props


def load_data(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_relationship_targets(data: Dict[str, Any]) -> Iterable[str]:
    ids = set()
    for collection in LABELS:
        ids.update(entity["id"] for entity in data.get(collection, []))
    for collection in LABELS:
        for entity in data.get(collection, []):
            for relationship in entity.get("relationships", []):
                if relationship.get("target") not in ids:
                    yield f"{entity['id']} -> {relationship.get('target')} is missing"


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest the Slay the Spire knowledge graph into Neo4j.")
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    data = load_data(Path(args.data))
    errors = list(validate_relationship_targets(data))
    if errors:
        raise SystemExit("Invalid relationship targets:\n" + "\n".join(errors))

    print("Data validation passed.")
    if args.dry_run:
        for collection in LABELS:
            print(f"{collection}: {len(data.get(collection, []))}")
        return

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    ingestor = GraphIngestor(uri, user, password)
    try:
        ingestor.create_constraints()
        ingestor.ingest(data)
        print("Neo4j graph ingestion complete.")
    finally:
        ingestor.close()


if __name__ == "__main__":
    main()
