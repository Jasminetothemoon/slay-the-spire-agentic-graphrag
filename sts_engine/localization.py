import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ZHS_PATH = ROOT / "data" / "localization_zhs.json"


REASON_TRANSLATIONS = [
    (r"Recommended: (.+?) \(score ([\d.]+), confidence ([\d.]+)\)\.", r"推荐：\1（分数 \2，置信度 \3）。"),
    (r"Detected: missing AoE\.", "检测到：缺少群体伤害。"),
    (r"Detected: low defense\.", "检测到：防御不足。"),
    (r"Detected: limited scaling\.", "检测到：成长能力有限。"),
    (r"Detected: low HP\.", "检测到：血量偏低。"),
    (r"No major deck-shape risk detected\.", "没有检测到明显卡组结构风险。"),
    (r"Graph synergy with current run: (.+?)\.", r"与当前局面存在图谱协同：\1。"),
    (r"Matches the current character card pool\.", "符合当前职业的卡池。"),
    (r"Fixes an AoE weakness before multi-enemy fights\.", "补足多敌人战斗前的群体伤害短板。"),
    (r"Improves a low-defense deck profile\.", "改善当前卡组防御不足的问题。"),
    (r"Adds scaling for midgame and boss fights\.", "为中期和 Boss 战补充成长能力。"),
    (r"Current HP is low, so safety is weighted higher\.", "当前血量偏低，因此更重视安全性。"),
    (r"Rest site is prioritized because current HP is low\.", "由于当前血量偏低，优先考虑休息点。"),
    (r"Gold total makes a shop route attractive\.", "当前金币较多，商店路线更有价值。"),
    (r"Card removal improves deck consistency\.", "删牌可以提升卡组稳定性。"),
    (r"Solid baseline value, but no decisive graph signal was found\.", "基础价值尚可，但没有找到决定性的图谱信号。"),
    (r"Estimated sequence output: (\d+) damage and (\d+) block\.", r"预计这组出牌造成 \1 点伤害并获得 \2 点格挡。"),
    (r"Covers the currently incoming damage\.", "可以覆盖当前即将受到的伤害。"),
    (r"AoE is valuable into the current multi-enemy board\.", "面对多个敌人时，群体伤害价值较高。"),
    (r"Likely removes at least one enemy this turn\.", "本回合大概率可以击杀至少一个敌人。"),
    (r"Weak reduces incoming attack pressure\.", "虚弱可以降低敌人的攻击压力。"),
    (r"Leaves about (\d+) unblocked incoming damage\.", r"大约还会剩余 \1 点未格挡伤害。"),
    (r"Potion use spends a limited resource\.", "使用药水会消耗有限资源。"),
    (r"Incoming damage is high enough that a defensive potion can preserve HP\.", "当前 incoming 伤害较高，防御药水可以保血。"),
]


@lru_cache(maxsize=1)
def load_zhs(path: str | None = None) -> Dict[str, Any]:
    target = Path(path) if path else DEFAULT_ZHS_PATH
    if not target.exists():
        return {"entities": {}, "mechanics": {}, "labels": {}}
    with open(target, "r", encoding="utf-8") as f:
        return json.load(f)


def entity_name(entity_id: str, fallback: str | None = None) -> str:
    data = load_zhs()
    return data.get("entities", {}).get(entity_id, {}).get("name") or fallback or entity_id


def mechanic_name(value: str) -> str:
    data = load_zhs()
    return data.get("mechanics", {}).get(value, value)


def label(value: str) -> str:
    data = load_zhs()
    return data.get("labels", {}).get(value, value)


def localize_text(text: str) -> str:
    localized = text
    for pattern, replacement in REASON_TRANSLATIONS:
        localized = re.sub(pattern, replacement, localized)
    data = load_zhs()
    for english, chinese in {
        "AoE": "群体伤害",
        "Block": "格挡",
        "Card Draw": "抽牌",
        "Frontload Damage": "前期输出",
        "Poison": "中毒",
        "Wrath": "愤怒",
        "Calm": "平静",
        "Focus": "集中",
        "Frost Orb": "冰霜充能球",
        "Lightning Orb": "闪电充能球",
    }.items():
        localized = localized.replace(english, chinese)
    for entity_id, item in data.get("entities", {}).items():
        english_name = item.get("english_name")
        if english_name and item.get("name"):
            localized = localized.replace(english_name, item["name"])
    return localized


def localize_score(score: Dict[str, Any]) -> Dict[str, Any]:
    option_id = score.get("option_id", "")
    localized = {
        "name": entity_name(option_id, score.get("name")),
        "reasons": [localize_text(reason) for reason in score.get("reasons", [])],
        "risks": [localize_text(risk) for risk in score.get("risks", [])],
    }
    return localized


def localize_response(response: Dict[str, Any]) -> Dict[str, Any]:
    option_scores = response.get("option_scores", [])
    return {
        "recommendation_name": entity_name(response.get("recommendation", ""), response.get("recommendation", "")),
        "reasoning": localize_text(response.get("reasoning", "")),
        "option_scores": [localize_score(score) for score in option_scores],
        "graph_context": [localize_graph_item(item) for item in response.get("graph_context", [])],
        "risk_report": localize_risk_report(response.get("risk_report", {})),
    }


def localize_graph_item(item: Dict[str, Any]) -> Dict[str, Any]:
    localized = dict(item)
    for key in ("owned_id", "option_id", "source", "target"):
        if key in localized:
            localized[f"{key}_name_zh"] = entity_name(str(localized[key]), str(localized[key]))
    for key in ("owned_name", "option_name", "source_name", "target_name"):
        if key in localized:
            localized[key] = localize_text(str(localized[key]))
    if "mechanic" in localized:
        localized["mechanic_name_zh"] = mechanic_name(str(localized["mechanic"]))
    if "mechanic_name" in localized:
        localized["mechanic_name"] = localize_text(str(localized["mechanic_name"]))
    if "relationship" in localized:
        localized["relationship_name_zh"] = label(str(localized["relationship"]))
    return localized


def localize_risk_report(risk_report: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "risks": [label(risk) for risk in risk_report.get("risks", [])],
        "summary": localize_text(risk_report.get("summary", "")),
        "deck_tags": [mechanic_name(tag) for tag in risk_report.get("deck_tags", [])],
    }


def localize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "character_class": label(state.get("character_class", "")),
        "deck": [entity_name(item, item) for item in state.get("deck", [])],
        "relics": [entity_name(item, item) for item in state.get("relics", [])],
        "potions": [entity_name(item, item) for item in state.get("potions", [])],
        "hand_cards": [entity_name(item, item) for item in state.get("hand_cards", [])],
        "options": [entity_name(item, item) for item in state.get("options", [])],
        "query_type": label(state.get("query_type", "")),
    }
