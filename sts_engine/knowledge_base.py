import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DATA_PATH = ROOT / "data" / "public_full_data.json"
SEED_DATA_PATH = ROOT / "data" / "sample_data.json"
DATA_PATH = PUBLIC_DATA_PATH if PUBLIC_DATA_PATH.exists() else SEED_DATA_PATH
STRATEGY_PATH = Path(__file__).resolve().parents[1] / "data" / "strategy" / "archetypes.json"


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

GAME_ID_ALIASES = {
    "purewater": "pure_water",
    "strike_r": "strike_ironclad",
    "defend_r": "defend_ironclad",
    "strike_g": "strike_silent",
    "defend_g": "defend_silent",
    "strike_b": "strike_defect",
    "defend_b": "defend_defect",
    "strike_p": "strike_watcher",
    "defend_p": "defend_watcher",
}

LOCALIZED_ALIASES = {
    "打击": {
        "ironclad": "strike_ironclad",
        "silent": "strike_silent",
        "defect": "strike_defect",
        "watcher": "strike_watcher",
    },
    "防御": {
        "ironclad": "defend_ironclad",
        "silent": "defend_silent",
        "defect": "defend_defect",
        "watcher": "defend_watcher",
    },
    "暴怒": "eruption",
    "警惕": "vigilance",
    "发泄": "tantrum",
    "停顿": "halt",
    "至纯之水": "pure_water",
    "药水栏": None,
}


def normalize_id(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def repair_mojibake(value: str) -> str:
    if not value:
        return value
    try:
        repaired = value.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value
    return repaired if repaired != value else value


class KnowledgeBase:
    def __init__(self, data: Dict[str, Any], strategy_data: Dict[str, Any] | None = None):
        self.data = data
        self.strategy_data = strategy_data or {"archetypes": []}
        self.metadata = data.get("metadata", {})
        self.entities: Dict[str, Dict[str, Any]] = {}
        self.name_to_id: Dict[str, str] = {}
        self.name_to_ids: Dict[str, List[str]] = {}
        self.compact_to_id: Dict[str, str] = {}
        self._index_entities()

    def _index_entities(self) -> None:
        for collection in ENTITY_COLLECTIONS:
            for entity in self.data.get(collection, []):
                entity = dict(entity)
                entity["entity_type"] = collection[:-1] if collection.endswith("s") else collection
                entity_id = entity["id"]
                self.entities[entity_id] = entity
                for key in {normalize_id(entity_id), normalize_id(entity.get("name", entity_id))}:
                    self.name_to_id[key] = entity_id
                    self.name_to_ids.setdefault(key, []).append(entity_id)
                    self.compact_to_id.setdefault(key.replace("_", ""), entity_id)

    def resolve_id(self, value: str, character_class: str | None = None) -> Optional[str]:
        if not value:
            return None
        value = repair_mojibake(str(value))
        localized = LOCALIZED_ALIASES.get(value)
        if isinstance(localized, dict):
            localized_id = localized.get((character_class or "").lower())
            if localized_id:
                return localized_id
        if isinstance(localized, str):
            return localized
        if localized is None and value in LOCALIZED_ALIASES:
            return None
        key = normalize_id(value)
        if key in GAME_ID_ALIASES:
            return GAME_ID_ALIASES[key]
        if key in self.entities:
            return key
        candidates = self.name_to_ids.get(key, [])
        if candidates:
            if character_class:
                character_class = character_class.lower()
                for entity_id in candidates:
                    entity = self.entities.get(entity_id, {})
                    if entity.get("class") == character_class:
                        return entity_id
                for entity_id in candidates:
                    entity = self.entities.get(entity_id, {})
                    if entity.get("class") in {"any", "colorless", None}:
                        return entity_id
            return candidates[0]
        compact_id = self.compact_to_id.get(key.replace("_", ""))
        if compact_id:
            return compact_id
        return None

    def resolve_many(self, values: Iterable[str], character_class: str | None = None) -> List[str]:
        resolved = []
        for value in values:
            entity_id = self.resolve_id(value, character_class)
            if entity_id:
                resolved.append(entity_id)
        return resolved

    def get(self, value: str, character_class: str | None = None) -> Optional[Dict[str, Any]]:
        entity_id = self.resolve_id(value, character_class) or value
        entity = self.entities.get(entity_id)
        return dict(entity) if entity else None

    def option_entities(self, options: Iterable[str], character_class: str | None = None) -> List[Dict[str, Any]]:
        entities = []
        for option in options:
            entity = self.get(option, character_class)
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
                        "provenance_source": relationship.get("source", entity.get("source", "unknown")),
                        "source_url": relationship.get("source_url", entity.get("source_url", "")),
                        "confidence": float(relationship.get("confidence", entity.get("confidence", 0.5))),
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

    def find_synergies(
        self, owned_items: Iterable[str], options: Iterable[str], character_class: str | None = None
    ) -> List[Dict[str, Any]]:
        owned_ids = self.resolve_many(owned_items, character_class)
        option_entities = self.option_entities(options, character_class)
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
                                "owned_source": owned.get("provenance_source", "unknown"),
                                "owned_source_url": owned.get("source_url", ""),
                                "owned_confidence": owned.get("confidence", 0.5),
                                "option_source": opt.get("provenance_source", "unknown"),
                                "option_source_url": opt.get("source_url", ""),
                                "option_confidence": opt.get("confidence", 0.5),
                            }
                        )
        return evidence

    def strategy_matches(self, state: Dict[str, Any], options: Iterable[str]) -> Dict[str, List[Dict[str, Any]]]:
        character_class = state.get("character_class", "").lower()
        owned_ids = set(self.resolve_many(state.get("deck", []), character_class))
        owned_ids.update(self.resolve_many(state.get("relics", []), character_class))
        option_entities = self.option_entities(options, character_class)
        option_ids = {option["id"] for option in option_entities}
        matches: Dict[str, List[Dict[str, Any]]] = {option["id"]: [] for option in option_entities}
        risk_tags = set(self.risk_tags(state))

        for archetype in self.strategy_data.get("archetypes", []):
            if archetype.get("class") not in {"any", character_class}:
                continue
            for rule in archetype.get("rules", []):
                owned_any = set(rule.get("when_owned_any", []))
                target_any = set(rule.get("target_any", []))
                if owned_any and not owned_ids.intersection(owned_any):
                    continue
                for option_id in option_ids.intersection(target_any):
                    matches.setdefault(option_id, []).append(
                        {
                            "type": "archetype_rule",
                            "archetype_id": archetype["id"],
                            "archetype_name": archetype["name"],
                            "rule_id": rule["id"],
                            "bonus": float(rule.get("bonus", 0)),
                            "reason": rule.get("reason", "Matches a curated archetype rule."),
                        }
                    )

            for risk, targets in archetype.get("covers_risks", {}).items():
                if risk not in risk_tags:
                    continue
                for option_id in option_ids.intersection(set(targets)):
                    matches.setdefault(option_id, []).append(
                        {
                            "type": "risk_cover",
                            "archetype_id": archetype["id"],
                            "archetype_name": archetype["name"],
                            "risk": risk,
                            "bonus": 10.0,
                            "reason": f"{self.entities.get(option_id, {}).get('name', option_id)} covers {risk} for {archetype['name']}.",
                        }
                    )

        return {option_id: items for option_id, items in matches.items() if items}

    def risk_tags(self, state: Dict[str, Any]) -> List[str]:
        deck_ids = self.resolve_many(state.get("deck", []), state.get("character_class", "").lower())
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
        data = json.load(f)
    strategy_path = os.getenv("STS_STRATEGY_PATH", str(STRATEGY_PATH))
    strategy_data = {"archetypes": []}
    if strategy_path and Path(strategy_path).exists():
        with open(strategy_path, "r", encoding="utf-8") as f:
            strategy_data = json.load(f)
    return KnowledgeBase(data, strategy_data)
