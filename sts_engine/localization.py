import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ZHS_PATH = ROOT / "data" / "localization_zhs.json"


REASON_TRANSLATIONS = [
    (r"Pick (.+?)\.", r"推荐选择：\1。"),
    (r"Primary archetype signal: (.+?)\.", r"主要流派信号：\1。"),
    (r"Recommended: (.+?) \(score ([\d.]+), confidence ([\d.]+)\)\.", r"推荐：\1（分数 \2，置信度 \3）。"),
    (r"Detected: missing AoE\.", "检测到：缺少群体伤害。"),
    (r"Detected: low defense\.", "检测到：防御不足。"),
    (r"Detected: limited scaling\.", "检测到：成长能力有限。"),
    (r"Detected: low HP\.", "检测到：血量偏低。"),
    (r"No major deck-shape risk detected\.", "没有检测到明显卡组结构风险。"),
    (r"Graph synergy with current run: (.+?)\.", r"与当前局面存在图谱协同：\1。"),
    (r"Archetype fit: (.+?)\.", r"契合流派：\1。"),
    (r"Matches the current character card pool\.", "符合当前职业的卡池。"),
    (r"Fixes an AoE weakness before multi-enemy fights\.", "补足多敌人战斗前的群体伤害短板。"),
    (r"Improves a low-defense deck profile\.", "改善当前卡组防御不足的问题。"),
    (r"Adds scaling for midgame and boss fights\.", "为中期和 Boss 战补充成长能力。"),
    (r"Current HP is low, so safety is weighted higher\.", "当前血量偏低，因此更重视安全性。"),
    (r"Rest site is prioritized because current HP is low\.", "由于当前血量偏低，优先考虑休息点。"),
    (r"Gold total makes a shop route attractive\.", "当前金币较多，商店路线更有价值。"),
    (r"Gold is too low to rely on card removal\.", "金币太少，不能优先依赖删牌。"),
    (r"The deck is still small, so removal is less urgent than adding power\.", "当前卡组还小，补强战力比删牌更紧迫。"),
    (r"Gold is below a typical relic-buying threshold\.", "当前金币低于通常购买遗物的门槛。"),
    (r"Gold is low, so buying cards is constrained\.", "金币偏少，买牌空间有限。"),
    (r"Gold is low, so even potion buying is constrained\.", "金币偏少，即使买药水也要谨慎。"),
    (r"Low HP makes a safety potion more attractive\.", "血量偏低，保命药水的价值更高。"),
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
    (r"Top option, but monitor its listed risk before committing\.", "这是当前首选，但在确定前仍要留意列出的风险。"),
    (r"Best overall mix of score, confidence, strategy fit, and graph evidence\.", "这是分数、置信度、策略契合度和图谱证据综合最好的选择。"),
    (r"Lower priority because it trails the top option by ([\d.]+) points\.", r"优先级较低，因为它落后首选 \1 分。"),
    (r"Lower priority because it has weaker graph or strategy evidence for the current run\.", "优先级较低，因为它对当前局面的图谱或策略证据较弱。"),
    (r"Lower priority because it does not clearly advance the detected archetype or cover a major risk\.", "优先级较低，因为它没有明显推进当前流派，也没有覆盖主要风险。"),
    (r"Lower priority because of this risk: (.+)", r"优先级较低，因为存在这个风险：\1"),
    (r"Playable alternative, but its current-run payoff is less direct than the top recommendation\.", "可以作为备选，但对当前局面的收益不如首选直接。"),
    (r"Elite path is justified by current frontload, potions, HP, or a nearby rest site\.", "当前前期输出、药水、血量或附近火堆足以支撑精英路线。"),
    (r"Elite path is risky without enough frontload damage, potion support, or HP\.", "如果缺少前期输出、药水支持或血量，精英路线风险较高。"),
    (r"Route contains (\d+) forced elite encounter\(s\)\.", r"这条路线包含 \1 个强制精英战。"),
    (r"Optional elite branch preserves reward upside without fully locking in risk\.", "可选精英分支保留了奖励上限，同时不会完全锁死风险。"),
    (r"Campfire before elite gives a recovery or upgrade checkpoint\.", "精英前的火堆提供了回血或升级检查点。"),
    (r"Shop before elite can convert gold into potions or frontload\.", "精英前的商店可以把金币转化为药水或前期战力。"),
    (r"Forced multiple elites without a rest site is a high-variance route\.", "没有火堆却强制连续打多个精英，这条路线波动很高。"),
    (r"Campfire keeps upgrade/rest flexibility open\.", "火堆保留了升级或休息的灵活性。"),
    (r"Early hallway fights are valuable for card rewards before committing to elites\.", "早期普通战有助于先拿卡牌奖励，再决定是否挑战精英。"),
    (r"Events gain value after Act 1 because they can avoid bad hallway fights\.", "第一幕后事件价值更高，因为可以避开糟糕的普通战。"),
    (r"Too many early Act 1 events can delay finding attack cards\.", "第一幕太早走过多事件，可能拖慢寻找攻击牌的节奏。"),
    (r"Route has acceptable baseline value, but no decisive pathing signal was found\.", "这条路线基础价值尚可，但没有明显的路线决策信号。"),
    (r"Poison payoff is premium once the deck already applies Poison\.", "当卡组已经能稳定叠毒时，毒流收益牌的优先级很高。"),
    (r"Corpse Explosion gives Poison decks a high-impact AoE plan\.", "尸爆能给毒流卡组提供高影响力的群体伤害方案。"),
    (r"Shiv generation makes attack-count and Shiv payoff cards much stronger\.", "已有刀片生成后，攻击次数和刀片收益牌会明显变强。"),
    (r"Discard payoffs become reliable once the deck has repeatable discard outlets\.", "当卡组有稳定弃牌入口时，弃牌收益牌会更可靠。"),
    (r"Strength payoff is much better after the deck already has Strength sources\.", "当卡组已经有力量来源时，力量收益牌会好很多。"),
    (r"Block payoffs need a deck that can generate large Block totals consistently\.", "格挡收益牌需要卡组能稳定打出较高格挡。"),
    (r"Exhaust payoff converts card removal into draw, block, or free Skills\.", "消耗收益能把删牌转化为抽牌、格挡或免费技能收益。"),
    (r"Power payoffs scale harder once the deck has Power support, cost reduction, or Power draw\.", "当卡组有能力牌支持、费用减免或能力牌抽取时，能力收益会更强。"),
    (r"Zero-cost payoff needs enough cheap cards, recursion, or draw to outpace normal card picks\.", "零费收益需要足够廉价牌、回收或抽牌，才能超过普通选牌价值。"),
    (r"Focus and orb slots scale strongly once the deck reliably channels orbs\.", "当卡组能稳定生成充能球时，集中和球位成长价值很高。"),
    (r"Stance payoffs become reliable when the deck can enter and exit stances\.", "当卡组能稳定进出姿态时，姿态收益牌会更可靠。"),
    (r"Divinity payoffs are stronger once the deck has real Mantra access\.", "当卡组有真正的真言来源时，神格收益牌更强。"),
    (r"Retain payoffs become meaningful when the deck already holds cards across turns\.", "当卡组已经能跨回合保留手牌时，保留收益牌才更有意义。"),
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
        "explanation_panel": localize_explanation_panel(response.get("explanation_panel", {})),
        "option_scores": [localize_score(score) for score in option_scores],
        "graph_context": [localize_graph_item(item) for item in response.get("graph_context", [])],
        "risk_report": localize_risk_report(response.get("risk_report", {})),
    }


def localize_explanation_panel(panel: Dict[str, Any]) -> Dict[str, Any]:
    if not panel:
        return {}
    localized = dict(panel)
    localized["summary"] = localize_text(str(panel.get("summary", "")))
    current_plan = dict(panel.get("current_plan", {}))
    current_plan["character_class"] = label(str(current_plan.get("character_class", "")))
    current_plan["query_type"] = label(str(current_plan.get("query_type", "")))
    current_plan["deck_tags"] = [mechanic_name(str(tag)) for tag in current_plan.get("deck_tags", [])]
    current_plan["risk_tags"] = [label(str(risk)) for risk in current_plan.get("risk_tags", [])]
    current_plan["risk_summary"] = localize_text(str(current_plan.get("risk_summary", "")))
    current_plan["detected_archetypes"] = [
        {**item, "name": localize_text(str(item.get("name", "")))} for item in current_plan.get("detected_archetypes", [])
    ]
    localized["current_plan"] = current_plan

    why_pick = dict(panel.get("why_pick", {}))
    why_pick["name"] = entity_name(str(why_pick.get("option_id", "")), str(why_pick.get("name", "")))
    why_pick["main_reasons"] = [localize_text(str(reason)) for reason in why_pick.get("main_reasons", [])]
    why_pick["tradeoff"] = localize_text(str(why_pick.get("tradeoff", "")))
    localized["why_pick"] = why_pick

    localized["risk_coverage"] = [
        {
            **item,
            "risk": label(str(item.get("risk", ""))),
            "status": label(str(item.get("status", ""))),
            "explanation": localize_text(str(item.get("explanation", ""))),
        }
        for item in panel.get("risk_coverage", [])
    ]
    localized["graph_evidence"] = [localize_graph_item(item) for item in panel.get("graph_evidence", [])]
    localized["candidate_comparison"] = [
        {
            **item,
            "name": entity_name(str(item.get("option_id", "")), str(item.get("name", ""))),
            "best_reason": localize_text(str(item.get("best_reason", ""))),
            "why_not": localize_text(str(item.get("why_not", ""))),
            "risks": [localize_text(str(risk)) for risk in item.get("risks", [])],
        }
        for item in panel.get("candidate_comparison", [])
    ]
    return localized


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
