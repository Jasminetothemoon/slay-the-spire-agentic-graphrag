import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "sample_data.json"


ENTITY_COLLECTIONS = (
    "classes",
    "mechanics",
    "cards",
    "relics",
    "potions",
    "enemies",
    "archetypes",
    "shop_actions",
    "path_nodes",
)


def normalize_id(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


class KnowledgeBase:
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.metadata = data.get("metadata", {})
        self.entities: Dict[str, Dict[str, Any]] = {}
        self.name_to_id: Dict[str, str] = {}
        self._index_entities()

    def _index_entities(self) -> None:
        for collection in ENTITY_COLLECTIONS:
            for entity in self.data.get(collection, []):
                entity = dict(entity)
                entity["entity_type"] = collection[:-1] if collection.endswith("s") else collection
                entity_id = entity["id"]
                self.entities[entity_id] = entity
                self.name_to_id[normalize_id(entity_id)] = entity_id
                self.name_to_id[normalize_id(entity.get("name", entity_id))] = entity_id

    def resolve_id(self, value: str) -> Optional[str]:
        if not value:
            return None
        return self.name_to_id.get(normalize_id(value))

    def resolve_many(self, values: Iterable[str]) -> List[str]:
        resolved = []
        for value in values:
            entity_id = self.resolve_id(value)
            if entity_id:
                resolved.append(entity_id)
        return resolved

    def get(self, value: str) -> Optional[Dict[str, Any]]:
        entity_id = self.resolve_id(value) or value
        entity = self.entities.get(entity_id)
        return dict(entity) if entity else None

    def option_entities(self, options: Iterable[str]) -> List[Dict[str, Any]]:
        entities = []
        for option in options:
            entity = self.get(option)
            if entity:
                entities.append(entity)
            else:
                entities.append(
                    {
                        "id": normalize_id(option),
                        "name": option,
                        "entity_type": "unknown",
                        "base_value": 35,
                        "tags": [],
                        "relationships": [],
                    }
                )
        return entities

    def mechanics_for(self, entity_id: str) -> List[Dict[str, Any]]:
        entity = self.entities.get(entity_id, {})
        mechanics = []
        for relationship in entity.get("relationships", []):
            target = relationship.get("target")
            target_entity = self.entities.get(target, {})
            if target_entity.get("entity_type") == "mechanic":
                mechanics.append(
                    {
                        "source": entity_id,
                        "source_name": entity.get("name", entity_id),
                        "relationship": relationship.get("type", "RELATED_TO"),
                        "mechanic": target,
                        "mechanic_name": target_entity.get("name", target),
                        "weight": float(relationship.get("weight", 0.5)),
                    }
                )
        return mechanics

    def tags_for_ids(self, entity_ids: Iterable[str]) -> List[str]:
        tags = []
        for entity_id in entity_ids:
            entity = self.entities.get(entity_id, {})
            tags.extend(entity.get("tags", []))
            for relationship in entity.get("relationships", []):
                target = relationship.get("target")
                target_entity = self.entities.get(target, {})
                if target_entity.get("entity_type") == "mechanic":
                    tags.append(target)
        return sorted(set(tags))

    def find_synergies(self, owned_items: Iterable[str], options: Iterable[str]) -> List[Dict[str, Any]]:
        owned_ids = self.resolve_many(owned_items)
        option_entities = self.option_entities(options)
        owned_mechanics = []
        for entity_id in owned_ids:
            owned_mechanics.extend(self.mechanics_for(entity_id))

        evidence = []
        for option in option_entities:
            option_mechanics = self.mechanics_for(option["id"])
            for owned in owned_mechanics:
                for opt in option_mechanics:
                    if owned["mechanic"] == opt["mechanic"]:
                        evidence.append(
                            {
                                "type": "shared_mechanic",
                                "owned_id": owned["source"],
                                "owned_name": owned["source_name"],
                                "owned_relationship": owned["relationship"],
                                "option_id": option["id"],
                                "option_name": option["name"],
                                "option_relationship": opt["relationship"],
                                "mechanic": owned["mechanic"],
                                "mechanic_name": owned["mechanic_name"],
                                "weight": round((owned["weight"] + opt["weight"]) / 2, 3),
                            }
                        )
        return evidence

    def risk_tags(self, state: Dict[str, Any]) -> List[str]:
        deck_ids = self.resolve_many(state.get("deck", []))
        deck_tags = self.tags_for_ids(deck_ids)
        risks = []
        if "aoe" not in deck_tags:
            risks.append("no_aoe")
        if "block" not in deck_tags and "orb_frost" not in deck_tags:
            risks.append("low_defense")
        if "scaling_damage" not in deck_tags and (state.get("act", 1) >= 2 or state.get("current_floor", 1) > 16):
            risks.append("slow_scaling")
        if state.get("current_hp", 99) <= max(18, int(state.get("max_hp", 70) * 0.35)):
            risks.append("low_hp")
        if state.get("gold", 0) >= 150:
            risks.append("shop_ready")
        return risks

    def entity_counts(self) -> Dict[str, int]:
        return {collection: len(self.data.get(collection, [])) for collection in ENTITY_COLLECTIONS}


def default_data_path() -> str:
    return os.getenv("STS_KB_PATH", str(DATA_PATH))


@lru_cache(maxsize=4)
def load_knowledge_base(path: str | None = None) -> KnowledgeBase:
    path = path or default_data_path()
    with open(path, "r", encoding="utf-8") as f:
        return KnowledgeBase(json.load(f))
