import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASE_URL = "https://slaythespire.gg"
OUTPUT_PATH = ROOT / "data" / "full_public_data.json"

CARD_CLASSES = ["ironclad", "silent", "defect", "watcher", "colorless", "curse", "status"]
LIST_PAGES = {
    "relics": "/relics",
    "potions": "/potions",
    "monsters": "/monsters",
    "elites": "/elites",
    "bosses": "/bosses",
}

MECHANICS = [
    {"id": "poison", "name": "Poison", "keywords": ["poison"]},
    {"id": "vulnerable", "name": "Vulnerable", "keywords": ["vulnerable"]},
    {"id": "weak", "name": "Weak", "keywords": ["weak"]},
    {"id": "block", "name": "Block", "keywords": ["block"]},
    {"id": "strength", "name": "Strength", "keywords": ["strength"]},
    {"id": "dexterity", "name": "Dexterity", "keywords": ["dexterity"]},
    {"id": "draw", "name": "Card Draw", "keywords": ["draw", "draws"]},
    {"id": "discard", "name": "Discard", "keywords": ["discard"]},
    {"id": "exhaust", "name": "Exhaust", "keywords": ["exhaust"]},
    {"id": "energy", "name": "Energy", "keywords": ["energy"]},
    {"id": "aoe", "name": "AoE", "keywords": ["all enemies", "aoe", "all enemy"]},
    {"id": "shiv", "name": "Shiv", "keywords": ["shiv"]},
    {"id": "stance_wrath", "name": "Wrath", "keywords": ["wrath"]},
    {"id": "stance_calm", "name": "Calm", "keywords": ["calm"]},
    {"id": "orb_frost", "name": "Frost Orb", "keywords": ["frost"]},
    {"id": "orb_lightning", "name": "Lightning Orb", "keywords": ["lightning"]},
    {"id": "orb_dark", "name": "Dark Orb", "keywords": ["dark orb", "dark"]},
    {"id": "focus", "name": "Focus", "keywords": ["focus"]},
    {"id": "artifact", "name": "Artifact", "keywords": ["artifact"]},
    {"id": "retain", "name": "Retain", "keywords": ["retain"]},
    {"id": "x_cost", "name": "X-Cost", "keywords": ["x-cost", "x cost"]},
    {"id": "status_card", "name": "Status Card", "keywords": ["status", "burn", "dazed", "wound", "slimed"]},
    {"id": "frontload_damage", "name": "Frontload Damage", "keywords": ["deal", "damage"]},
    {"id": "low_frontload", "name": "Low Frontload", "keywords": []},
    {"id": "slow_scaling", "name": "Slow Scaling", "keywords": []},
]

RELATION_RULES = {
    "poison": "APPLIES",
    "vulnerable": "APPLIES",
    "weak": "APPLIES",
    "block": "APPLIES",
    "strength": "APPLIES",
    "dexterity": "APPLIES",
    "draw": "APPLIES",
    "discard": "APPLIES",
    "exhaust": "APPLIES",
    "energy": "APPLIES",
    "aoe": "APPLIES",
    "shiv": "APPLIES",
    "stance_wrath": "APPLIES",
    "stance_calm": "APPLIES",
    "orb_frost": "APPLIES",
    "orb_lightning": "APPLIES",
    "orb_dark": "APPLIES",
    "focus": "ENHANCES",
    "artifact": "APPLIES",
    "retain": "APPLIES",
    "x_cost": "SCALES_WITH",
    "status_card": "APPLIES",
    "frontload_damage": "APPLIES",
}


def slugify(value: str) -> str:
    value = value.strip().lower().replace("’", "").replace("'", "")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return re.sub(r"_+", "_", value).strip("_")


def clean_text(value: str) -> str:
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


class PublicWikiImporter:
    def __init__(self, base_url: str = BASE_URL, delay: float = 0.05):
        self.base_url = base_url.rstrip("/")
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "SlayTheSpireAgenticGraphRAG/0.2 (+https://github.com/Jasminetothemoon/slay-the-spire-agentic-graphrag)"
            }
        )

    def fetch(self, path_or_url: str) -> BeautifulSoup:
        url = urljoin(self.base_url, path_or_url)
        response = self.session.get(url, timeout=20)
        response.raise_for_status()
        time.sleep(self.delay)
        return BeautifulSoup(response.text, "html.parser")

    def collect_card_links(self) -> List[Dict[str, str]]:
        links = []
        for card_class in CARD_CLASSES:
            soup = self.fetch(f"/cards/{card_class}")
            for anchor in soup.select("a[href]"):
                href = anchor.get("href", "")
                if f"/cards/{card_class}/" not in href:
                    continue
                name = clean_text(anchor.get_text(" "))
                if not name or name.lower().startswith("view all"):
                    continue
                links.append({"name": self._strip_card_link_label(name, card_class), "url": urljoin(self.base_url, href), "class": card_class})
        return self._dedupe_links(links)

    def collect_links(self, collection: str, path: str) -> List[Dict[str, str]]:
        soup = self.fetch(path)
        links = []
        for anchor in soup.select("a[href]"):
            href = anchor.get("href", "")
            if f"/{collection}/" not in href:
                continue
            name = clean_text(anchor.get_text(" "))
            if name and not name.lower().startswith("image:"):
                links.append({"name": name, "url": urljoin(self.base_url, href)})
        return self._dedupe_links(links)

    def import_all(
        self,
        limit: Optional[int] = None,
        collections: Optional[set[str]] = None,
        output_path: Optional[Path] = None,
        checkpoint_every: int = 25,
    ) -> Dict[str, Any]:
        collections = collections or {"cards", "relics", "potions", "monsters", "elites", "bosses"}
        data = self._base_dataset()

        if "cards" in collections:
            card_links = self.collect_card_links()
            parsed_cards = self._parse_with_checkpoints(
                [("cards", link) for link in self._limit(card_links, limit)], data, output_path, checkpoint_every
            )
            data["cards"] = self._dedupe_entities(parsed_cards)

        for collection, path in LIST_PAGES.items():
            if collection not in collections:
                continue
            links = self.collect_links(collection, path)
            parsed = self._parse_with_checkpoints(
                [(collection, link) for link in self._limit(links, limit)], data, output_path, checkpoint_every
            )
            if collection in ("monsters", "elites", "bosses"):
                data["enemies"].extend(self._dedupe_entities(parsed))
            else:
                data[collection] = self._dedupe_entities(parsed)

        data["metadata"]["entity_counts"] = self._entity_counts(data)
        return data

    def collect_link_index(self) -> Dict[str, List[Dict[str, str]]]:
        index = {"cards": self.collect_card_links()}
        for collection, path in LIST_PAGES.items():
            index[collection] = self.collect_links(collection, path)
        return index

    def _parse_with_checkpoints(
        self,
        work_items: List[tuple[str, Dict[str, str]]],
        data: Dict[str, Any],
        output_path: Optional[Path],
        checkpoint_every: int,
    ) -> List[Dict[str, Any]]:
        parsed = []
        for idx, (collection, link) in enumerate(work_items, start=1):
            if collection == "cards":
                parsed.append(self.parse_card(link))
            else:
                parsed.append(self.parse_generic_entity(collection, link))
            if output_path and checkpoint_every and idx % checkpoint_every == 0:
                preview = dict(data)
                preview[collection if collection not in ("elites", "bosses") else "enemies"] = parsed
                preview["metadata"]["entity_counts"] = self._entity_counts(preview)
                self.write_dataset(preview, output_path)
        return parsed

    def write_dataset(self, data: Dict[str, Any], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def parse_card(self, link: Dict[str, str]) -> Dict[str, Any]:
        soup = self.fetch(link["url"])
        text_lines = self._main_text_lines(soup)
        name = self._h1(soup) or link["name"]
        description = self._quoted_description(text_lines) or self._line_after(text_lines, "Effect:")
        rarity = self._field_block(text_lines, "Rarity") or self._infer_card_rarity(text_lines, name)
        card_type = self._field_block(text_lines, "Type") or "Unknown"
        cost = self._field_block(text_lines, "Cost")
        deck = self._field_block(text_lines, "Deck") or link["class"]
        mechanics = self._detect_mechanics(" ".join([description, name]))
        relationships = self._relationships_for_mechanics(mechanics)
        relationships = self._promote_scaling_relationships(relationships, description)
        return {
            "id": self._unique_card_id(name, deck),
            "name": name,
            "class": slugify(deck),
            "type": card_type,
            "rarity": rarity,
            "energy_cost": self._parse_cost(cost),
            "base_value": self._base_value_for_card(rarity, card_type),
            "tags": mechanics,
            "description": description,
            "source_url": link["url"],
            "source": "slaythespire.gg",
            "confidence": 0.72,
            "relationships": relationships,
        }

    def parse_generic_entity(self, collection: str, link: Dict[str, str]) -> Dict[str, Any]:
        soup = self.fetch(link["url"])
        text_lines = self._main_text_lines(soup)
        name = self._h1(soup) or link["name"]
        body = " ".join(text_lines[:40])
        description = self._description_for(collection, text_lines)
        mechanics = self._detect_mechanics(" ".join([name, description, body]))
        entity: Dict[str, Any] = {
            "id": slugify(name),
            "name": name,
            "base_value": self._base_value_for(collection),
            "tags": mechanics,
            "description": description,
            "source_url": link["url"],
            "source": "slaythespire.gg",
            "confidence": 0.68,
            "relationships": self._relationships_for_mechanics(mechanics),
        }
        if collection == "relics":
            rarity, class_name = self._parse_relic_meta(text_lines)
            entity.update({"tier": rarity or "Unknown", "class": slugify(class_name or "any")})
        elif collection == "potions":
            entity.update({"rarity": self._first_non_field_line(text_lines, fallback="Unknown")})
        elif collection in ("monsters", "elites", "bosses"):
            entity.update({"type": self._enemy_type(collection), "act": self._parse_act(body)})
            entity["relationships"].extend(self._enemy_risk_relationships(body))
        return entity

    def _base_dataset(self) -> Dict[str, Any]:
        return {
            "metadata": {
                "game": "sts1",
                "patch_version": "2.3",
                "source": "slaythespire.gg",
                "source_url": self.base_url,
                "confidence": 0.7,
                "description": "Public wiki import generated by scripts/import_public_wiki.py.",
            },
            "classes": [
                {"id": "ironclad", "name": "Ironclad"},
                {"id": "silent", "name": "Silent"},
                {"id": "defect", "name": "Defect"},
                {"id": "watcher", "name": "Watcher"},
                {"id": "colorless", "name": "Colorless"},
                {"id": "curse", "name": "Curse"},
                {"id": "status_class", "name": "Status"},
            ],
            "mechanics": [{"id": item["id"], "name": item["name"], "tags": []} for item in MECHANICS],
            "cards": [],
            "relics": [],
            "potions": [],
            "enemies": [],
            "archetypes": [],
            "shop_actions": [
                {"id": "remove_card", "name": "Remove a Card", "base_value": 68, "tags": ["deck_control"]},
                {"id": "buy_potion", "name": "Buy Potion", "base_value": 48, "tags": ["elite_safety"]},
                {"id": "skip_shop", "name": "Skip", "base_value": 25, "tags": ["save_gold"]},
            ],
            "path_nodes": [
                {"id": "elite", "name": "Elite", "base_value": 62, "tags": ["reward", "risk"]},
                {"id": "rest", "name": "Rest Site", "base_value": 54, "tags": ["heal", "upgrade"]},
                {"id": "shop", "name": "Shop", "base_value": 52, "tags": ["spend_gold"]},
                {"id": "unknown", "name": "Unknown", "base_value": 45, "tags": ["variance"]},
                {"id": "monster", "name": "Monster", "base_value": 42, "tags": ["card_reward"]},
            ],
        }

    def _main_text_lines(self, soup: BeautifulSoup) -> List[str]:
        body = soup.find("main") or soup.body or soup
        lines = [clean_text(line) for line in body.get_text("\n").splitlines()]
        ignored_prefixes = ("SlayTheSpire", "Fast, searchable", "Card Wiki", "Project", "Privacy Policy", "©")
        return [line for line in lines if line and not line.startswith(ignored_prefixes)]

    def _h1(self, soup: BeautifulSoup) -> str:
        h1 = soup.find("h1")
        return clean_text(h1.get_text(" ")) if h1 else ""

    def _quoted_description(self, lines: List[str]) -> str:
        for line in lines:
            if line.startswith('"') and line.endswith('"'):
                return line.strip('"')
        return ""

    def _field(self, lines: List[str], field: str) -> str:
        prefix = f"{field}:"
        for line in lines:
            if line.startswith(prefix):
                return clean_text(line.split(":", 1)[1])
        return ""

    def _field_block(self, lines: List[str], field: str) -> str:
        inline = self._field(lines, field)
        if inline:
            return inline
        marker = f"{field}:"
        for idx, line in enumerate(lines):
            if line == marker:
                return self._next_content_line(lines, idx + 1)
        return ""

    def _line_after(self, lines: List[str], marker: str) -> str:
        for line in lines:
            if marker in line:
                return clean_text(line.split(marker, 1)[1])
        return ""

    def _first_non_field_line(self, lines: List[str], fallback: str = "") -> str:
        skip = {"Search`⌘K`☰"}
        for line in lines:
            if line in skip or line.startswith("#"):
                continue
            if ":" not in line and not line.lower().startswith("image:"):
                return line
        return fallback

    def _infer_card_rarity(self, lines: List[str], card_name: str) -> str:
        rarities = {"Starter", "Common", "Uncommon", "Rare", "Special", "Curse", "Status"}
        try:
            start = lines.index(card_name) + 1
        except ValueError:
            start = 0
        for line in lines[start : start + 5]:
            if line in rarities:
                return line
        return "Unknown"

    def _description_for(self, collection: str, lines: List[str]) -> str:
        if collection == "relics":
            for idx, line in enumerate(lines):
                if line.startswith("Rarity:"):
                    return self._next_content_line(lines, idx + 1)
        if collection in ("elites", "bosses"):
            for idx, line in enumerate(lines):
                if line == "Description":
                    return self._next_content_line(lines, idx + 1)
        for line in lines:
            if len(line) > 24 and not line.lower().startswith("image:"):
                return line
        return ""

    def _next_content_line(self, lines: List[str], start: int) -> str:
        for line in lines[start:]:
            if line and not line.lower().startswith("image:") and not line.startswith("##"):
                return line
        return ""

    def _parse_relic_meta(self, lines: List[str]) -> tuple[str, str]:
        for line in lines:
            if line.startswith("Rarity:"):
                rarity = line.split("Rarity:", 1)[1]
                class_name = ""
                if "Class:" in rarity:
                    rarity, class_name = rarity.split("Class:", 1)
                return clean_text(rarity), clean_text(class_name)
        return "", ""

    def _parse_cost(self, value: str) -> Any:
        value = value.strip()
        if value.lower() in {"x", "x-cost"}:
            return "X"
        try:
            return int(value)
        except ValueError:
            return None

    def _parse_act(self, text: str) -> Optional[int]:
        text = text.lower()
        roman = {"act i": 1, "act ii": 2, "act iii": 3, "act iv": 4}
        for key, value in roman.items():
            if key in text:
                return value
        match = re.search(r"act\s+(\d)", text)
        return int(match.group(1)) if match else None

    def _detect_mechanics(self, text: str) -> List[str]:
        lower = text.lower()
        found = []
        for mechanic in MECHANICS:
            if any(keyword in lower for keyword in mechanic["keywords"]):
                found.append(mechanic["id"])
        return sorted(set(found))

    def _relationships_for_mechanics(self, mechanics: Iterable[str]) -> List[Dict[str, Any]]:
        relationships = []
        for mechanic in mechanics:
            relationships.append(
                {
                    "type": RELATION_RULES.get(mechanic, "APPLIES"),
                    "target": mechanic,
                    "weight": 0.65,
                }
            )
        return relationships

    def _promote_scaling_relationships(
        self, relationships: List[Dict[str, Any]], description: str
    ) -> List[Dict[str, Any]]:
        lower = description.lower()
        scaling_markers = ("double", "triple", "multiply", "increase", "gain focus", "gain strength")
        if not any(marker in lower for marker in scaling_markers):
            return relationships
        scaling_targets = {"poison", "strength", "focus", "orb_frost", "orb_lightning", "orb_dark"}
        for relationship in relationships:
            if relationship.get("target") in scaling_targets:
                relationship["type"] = "SCALES_WITH"
                relationship["weight"] = max(float(relationship.get("weight", 0.65)), 0.85)
        return relationships

    def _enemy_risk_relationships(self, body: str) -> List[Dict[str, Any]]:
        lower = body.lower()
        relationships = []
        if "punishes" in lower or "enrage" in lower:
            relationships.append({"type": "PUNISHES", "target": "low_frontload", "weight": 0.8})
        if "all enemies" in lower or "multi" in lower or "adds" in lower:
            relationships.append({"type": "GOOD_AGAINST", "target": "aoe", "weight": 0.7})
        if "scaling" in lower or "grows" in lower:
            relationships.append({"type": "PUNISHES", "target": "slow_scaling", "weight": 0.7})
        return relationships

    def _base_value_for_card(self, rarity: str, card_type: str) -> int:
        score = {"Starter": 42, "Common": 55, "Uncommon": 63, "Rare": 72}.get(rarity, 50)
        if card_type == "Power":
            score += 3
        return score

    def _base_value_for(self, collection: str) -> int:
        return {"relics": 64, "potions": 48, "monsters": 45, "elites": 55, "bosses": 70}.get(collection, 45)

    def _enemy_type(self, collection: str) -> str:
        return {"monsters": "monster", "elites": "elite", "bosses": "boss"}.get(collection, "enemy")

    def _strip_card_link_label(self, value: str, card_class: str) -> str:
        for rarity in ("Starter", "Common", "Uncommon", "Rare"):
            value = value.replace(f" {rarity} {card_class}", "")
        return clean_text(value)

    def _unique_card_id(self, name: str, deck: str) -> str:
        base = slugify(name)
        deck_id = slugify(deck)
        reserved_ids = {item["id"] for item in MECHANICS}
        if base in {"strike", "defend"} and deck_id:
            return f"{base}_{deck_id}"
        if base in reserved_ids:
            return f"{base}_card"
        return base

    def _dedupe_links(self, links: List[Dict[str, str]]) -> List[Dict[str, str]]:
        seen = set()
        deduped = []
        for link in links:
            key = urlparse(link["url"]).path.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(link)
        return deduped

    def _dedupe_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        deduped = []
        for entity in entities:
            entity_id = entity["id"]
            if entity_id in seen:
                continue
            seen.add(entity_id)
            deduped.append(entity)
        return deduped

    def _limit(self, items: List[Dict[str, str]], limit: Optional[int]) -> List[Dict[str, str]]:
        return items[:limit] if limit else items

    def _entity_counts(self, data: Dict[str, Any]) -> Dict[str, int]:
        return {
            key: len(data.get(key, []))
            for key in ("classes", "mechanics", "cards", "relics", "potions", "enemies", "archetypes", "shop_actions", "path_nodes")
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import public Slay the Spire wiki data into the project schema.")
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--limit", type=int, default=None, help="Limit detail pages per collection for quick smoke tests.")
    parser.add_argument("--delay", type=float, default=0.05)
    parser.add_argument(
        "--collections",
        default="cards,relics,potions,monsters,elites,bosses",
        help="Comma-separated subset: cards,relics,potions,monsters,elites,bosses.",
    )
    parser.add_argument("--links-only", action="store_true", help="Only collect list-page links and write them as JSON.")
    parser.add_argument("--checkpoint-every", type=int, default=25)
    args = parser.parse_args()

    importer = PublicWikiImporter(delay=args.delay)
    output = Path(args.output)

    if args.links_only:
        link_index = importer.collect_link_index()
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(link_index, f, ensure_ascii=False, indent=2)
        print(json.dumps({key: len(value) for key, value in link_index.items()}, indent=2))
        print(f"Wrote {output}")
        return

    collections = {item.strip() for item in args.collections.split(",") if item.strip()}
    data = importer.import_all(
        limit=args.limit,
        collections=collections,
        output_path=output,
        checkpoint_every=args.checkpoint_every,
    )
    importer.write_dataset(data, output)
    print(json.dumps(data["metadata"]["entity_counts"], indent=2))
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
