import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sts_engine.knowledge_base import GAME_ID_ALIASES, normalize_id

DEFAULT_JAR = ROOT / "mod-bridge" / "libs" / "desktop-1.0.jar"
DEFAULT_DATA = ROOT / "data" / "public_full_data.json"
DEFAULT_OUTPUT = ROOT / "data" / "localization_zhs.json"


COLLECTIONS = {
    "cards": "cards",
    "relics": "relics",
    "potions": "potions",
    "monsters": "enemies",
}


def read_jar_json(jar_path: Path, member: str) -> Dict[str, Any]:
    with zipfile.ZipFile(jar_path) as jar:
        with jar.open(member) as f:
            return json.loads(f.read().decode("utf-8-sig"))


def add_entry(target: Dict[str, Dict[str, str]], entity_id: str, name: str | None, description: str | None = None) -> None:
    if not entity_id or not name:
        return
    item = target.setdefault(entity_id, {})
    item["name"] = name
    item.setdefault("english_name", "")
    if description:
        item["description"] = description


def localization_candidates(entity: Dict[str, Any]) -> list[str]:
    values = [entity.get("id", ""), entity.get("name", "")]
    game_aliases = {target: alias for alias, target in GAME_ID_ALIASES.items()}
    if entity.get("id") in game_aliases:
        values.append(game_aliases[entity["id"]])
    source_url = entity.get("source_url", "")
    if "/" in source_url:
        values.append(source_url.rstrip("/").split("/")[-1])
    return [value for value in values if value]


def match_entities(public_data: Dict[str, Any], raw_localization: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    localized: Dict[str, Dict[str, str]] = {}
    name_index: Dict[str, Dict[str, Any]] = {}
    id_index: Dict[str, Dict[str, Any]] = {}
    compact_id_index: Dict[str, Dict[str, Any]] = {}
    for raw_id, item in raw_localization.items():
        normalized_raw_id = normalize_id(raw_id)
        id_index[normalized_raw_id] = item
        compact_id_index[normalized_raw_id.replace("_", "")] = item
        if item.get("NAME"):
            name_index[normalize_id(item["NAME"])] = item

    for loc_file, collection in COLLECTIONS.items():
        for entity in public_data.get(collection, []):
            matched = None
            for candidate in localization_candidates(entity):
                key = normalize_id(candidate)
                matched = id_index.get(key) or compact_id_index.get(key.replace("_", "")) or name_index.get(key)
                if matched:
                    break
            if matched:
                add_entry(localized, entity["id"], matched.get("NAME"), matched.get("DESCRIPTION"))
                localized[entity["id"]]["english_name"] = entity.get("name", entity["id"])

    return localized


def main() -> None:
    parser = argparse.ArgumentParser(description="Build simplified Chinese localization snapshot from the local game jar.")
    parser.add_argument("--jar", default=str(DEFAULT_JAR))
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    jar_path = Path(args.jar)
    if not jar_path.exists():
        raise SystemExit(f"Missing game jar: {jar_path}")

    with open(args.data, "r", encoding="utf-8") as f:
        public_data = json.load(f)

    raw_by_file = {
        name: read_jar_json(jar_path, f"localization/zhs/{name}.json")
        for name in ("cards", "relics", "potions", "monsters")
    }
    merged_raw = {}
    for data in raw_by_file.values():
        merged_raw.update(data)

    entities = match_entities(public_data, merged_raw)
    mechanics = {
        "aoe": "群体伤害",
        "block": "格挡",
        "draw": "抽牌",
        "discard": "弃牌",
        "energy": "能量",
        "frontload_damage": "前期输出",
        "poison": "中毒",
        "strength": "力量",
        "stance_wrath": "愤怒",
        "stance_calm": "平静",
        "focus": "集中",
        "orb_frost": "冰霜充能球",
        "orb_lightning": "闪电充能球",
        "scaling_damage": "成长输出",
        "retain": "保留",
        "weak": "虚弱",
        "vulnerable": "易伤",
    }
    labels = {
        "ironclad": "铁甲战士",
        "silent": "静默猎手",
        "defect": "故障机器人",
        "watcher": "观者",
        "card_pick": "选牌",
        "relic_pick": "选遗物",
        "shop": "商店",
        "pathing": "路线",
        "combat": "战斗",
        "no_aoe": "缺少群体伤害",
        "low_defense": "防御不足",
        "slow_scaling": "成长能力不足",
        "low_hp": "血量偏低",
        "shop_ready": "金币适合进商店",
    }

    output = {
        "metadata": {
            "language": "zhs",
            "source": "local_game_jar",
            "source_path": str(jar_path),
            "entity_count": len(entities),
        },
        "entities": entities,
        "mechanics": mechanics,
        "labels": labels,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps(output["metadata"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
