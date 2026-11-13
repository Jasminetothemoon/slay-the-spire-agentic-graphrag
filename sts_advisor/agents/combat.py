"""战斗顾问：规划这一回合怎么出牌。

分工（docs/v2_design.md 改动点 7）：
- 模型负责规划和取舍：抢血还是防守、先打哪张、打谁。
- 数值和事实不让模型凭印象：它通过 settle 工具试算，通过 draw_odds 工具查抽牌概率，通过 enemy_info 工具查敌人的招式。
- 模型通过 submit_plan 工具提交计划。计划由程序核对后才算数，不过关就把原因作为工具结果退回去。
- 展示给玩家的数字来自程序的结算，不来自模型的文字。

最终答案也走工具调用，是为了不依赖各家模型各不相同的结构化输出功能。
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

from sts_advisor.agents import loop
from sts_advisor.agents.llm import Model, ToolCall, ToolResult, ToolSpec
from sts_advisor.ingest.visible_state import Decision, VisibleState
from sts_advisor.knowledge import monsters
from sts_advisor.tools.draw_odds import draw_probability
from sts_advisor.tools.enumerate import best_single_turn
from sts_advisor.tools.settle import Play, SettleResult, SettleUnavailable, all_enemies_dead, settle

SYSTEM_PROMPT = """你是《杀戮尖塔》的战斗顾问。玩家是新手，正在打一场战斗，轮到他出牌。你的任务是规划这一回合怎么出牌，并用新手听得懂的话说明为什么。

你会收到一份 JSON，描述玩家此刻在屏幕上能看到的全部信息：手牌、能量、血量和格挡、敌人的血量和本回合意图、抽牌堆和弃牌堆里各有哪些牌（顺序未知）、遗物、药水。你只知道这些。

卡牌的写法：游戏内部编号，升级过的在后面加 +，例如 "Bash+"。target 是敌人在 monsters 里的 index；不需要指定目标的牌填 null。

工具：
- settle：给一串出牌，返回打完之后每个敌人剩多少血、是否打死、你的格挡、敌人按本回合意图行动后你掉多少血、剩余能量；出牌不合法时告诉你是第几步、为什么。凡是涉及数字的判断，先用它试算，不要心算——伤害受易伤、力量、遗物等很多因素影响，心算容易错。想比较几种打法时，每种都试算一次。
- draw_odds：查接下来抽若干张牌时，抽到指定牌的概率。计划里有抽牌的牌、并且后续打法取决于抽到什么时用它。
- enemy_info：按敌人的 id 查它有哪些招式、按什么规则出招、有什么要特别注意的机制。打精英和 Boss 时先查一次；需要判断敌人之后几回合会做什么时也用它。查不到的敌人，不要凭印象断言它之后的招式，把依赖这一点的地方写进 uncertain。
- submit_plan：想清楚之后，用它提交最终计划。每次回答都要以调用它结束；只写文字不调用它，玩家什么也收不到。

怎么规划：
- 先看能不能这回合打死敌人。能打死的敌人不会再行动，通常比防守更划算。
- 不能打死时，在输出伤害和减少掉血之间权衡。两个方向都检查一遍：这样打会不会太贪（白白掉很多血），会不会太怂（能安全输出却只顾防守，拖长战斗）。
- 出牌顺序会改变结果，例如先上易伤再攻击。拿不准顺序时用 settle 比较。
- 如果计划里有会抽牌的牌，把它放在前面打，并用 tentative_from 标出从第几步起只是暂定：抽到新牌后玩家会带着新局面再来问一次。
- 输入里 unsupported_cards 列出的牌，settle 无法试算。可以把它们放进计划，但要在 uncertain 里说明这部分没有经过试算。

submit_plan 的各字段：
- plays：本回合完整的出牌顺序。空数组表示直接结束回合。
- tentative_from：从 plays 的第几步（从 0 数）起是暂定的；没有暂定部分填 null。
- summary：一句话结论，告诉玩家下一步做什么。
- reasons：两到三条理由，写给新手看，术语第一次出现时顺带解释。不要在理由里自己报具体数字，数字由程序根据试算结果填给玩家。
- risks：这样打的代价，没有就留空数组。
- uncertain：你没把握的地方，没有就留空数组。

提交的计划会被程序重新结算一遍。不合法时，原因会作为 submit_plan 的结果退回来，请修正后重新提交。"""

_PLAYS_SCHEMA: dict[str, Any] = {
    "type": "array",
    "description": "按顺序打出的牌",
    "items": {
        "type": "object",
        "properties": {
            "card": {"type": "string", "description": "卡牌的内部编号，升级过的加 +，例如 Bash+"},
            "target": {
                "anyOf": [{"type": "integer"}, {"type": "null"}],
                "description": "敌人的 index；不需要目标的牌填 null",
            },
        },
        "required": ["card", "target"],
        "additionalProperties": False,
    },
}

SETTLE_TOOL = ToolSpec(
    name="settle",
    description=(
        "结算一串出牌，返回打完之后的结果：每个敌人剩多少血、是否打死、你的格挡、"
        "敌人按本回合意图行动后你掉多少血、剩余能量。出牌不合法时返回第几步、为什么。"
        "凡是涉及数字的判断都先调用它，不要心算；比较几种打法时每种调用一次。"
        "plays 为空数组表示什么都不打，直接看敌人行动后的结果。"
    ),
    parameters={
        "type": "object",
        "properties": {"plays": _PLAYS_SCHEMA},
        "required": ["plays"],
        "additionalProperties": False,
    },
)

DRAW_ODDS_TOOL = ToolSpec(
    name="draw_odds",
    description=(
        "计算接下来抽若干张牌时，至少抽到指定牌中若干张的概率。抽牌堆抽空后会接着从弃牌堆里抽。"
        "计划里有抽牌的牌、并且后续打法取决于抽到什么时调用。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "cards": {
                "type": "array",
                "items": {"type": "string"},
                "description": '想抽到的牌，写法同 settle，例如 ["Bash+", "Shrug It Off"]',
            },
            "draws": {"type": "integer", "description": "要抽几张"},
            "at_least": {"type": "integer", "description": "至少抽到几张才算数，通常是 1"},
        },
        "required": ["cards", "draws", "at_least"],
        "additionalProperties": False,
    },
)

SUBMIT_TOOL = ToolSpec(
    name="submit_plan",
    description="提交本回合的最终计划。想清楚并试算过之后调用，每次回答都以它结束。计划不合法时原因会退回来。",
    parameters={
        "type": "object",
        "properties": {
            "plays": {**_PLAYS_SCHEMA, "description": "本回合完整的出牌顺序。空数组表示直接结束回合"},
            "tentative_from": {
                "anyOf": [{"type": "integer"}, {"type": "null"}],
                "description": "从 plays 的第几步（从 0 数）起是暂定的；没有填 null",
            },
            "summary": {"type": "string", "description": "一句话结论"},
            "reasons": {"type": "array", "items": {"type": "string"}, "description": "两到三条理由，写给新手"},
            "risks": {"type": "array", "items": {"type": "string"}, "description": "这样打的代价"},
            "uncertain": {"type": "array", "items": {"type": "string"}, "description": "没把握的地方"},
        },
        "required": ["plays", "tentative_from", "summary", "reasons", "risks", "uncertain"],
        "additionalProperties": False,
    },
)

ENEMY_INFO_TOOL = ToolSpec(
    name="enemy_info",
    description=(
        "查一个敌人的资料：招式和数值、出招规则、要特别注意的机制。"
        "打精英和 Boss 时先调用一次；需要判断敌人之后几回合会做什么时调用。没有收录的敌人会明确告诉你查不到。"
    ),
    parameters={
        "type": "object",
        "properties": {"monster_id": {"type": "string", "description": "敌人的 id，取自输入里 monsters[].id"}},
        "required": ["monster_id"],
        "additionalProperties": False,
    },
)

TOOLS = [SETTLE_TOOL, DRAW_ODDS_TOOL, ENEMY_INFO_TOOL, SUBMIT_TOOL]

NO_SUBMIT = loop.no_submit_message("submit_plan")


@dataclass
class CombatAdvice:
    source: str  # "model"：模型的计划通过了核对；"enumeration"：降级为单回合枚举；"none"：给不出建议
    plays: list[Play] = field(default_factory=list)
    tentative_from: int | None = None
    summary: str = ""
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    uncertain: list[str] = field(default_factory=list)
    result: SettleResult | None = None  # 程序对 plays 的结算结果，展示用的数字从这里取
    tier: str = ""
    model_calls: int = 0
    tool_calls: int = 0
    pushbacks: int = 0
    note: str = ""  # 降级或核对的说明


def pick_tier(state: VisibleState) -> str:
    """普通小怪战用便宜的档位，精英和 Boss 用强的档位。"""
    room = str(state.game.get("room_type", ""))
    return "strong" if ("Elite" in room or "Boss" in room) else "fast"


def _card_ref(card: dict[str, Any]) -> str:
    return card.get("id", "") + "+" * int(card.get("upgrades", 0))


def _pile(cards: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(_card_ref(c) for c in cards).items()))


def _powers(powers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"id": p.get("id"), "amount": p.get("amount")} for p in powers or []]


def _attack(monster: dict[str, Any]) -> dict[str, int] | None:
    damage = monster.get("move_adjusted_damage")
    if damage is None or damage < 0:
        return None  # 本回合不攻击，或意图被隐藏
    return {"damage": damage, "hits": monster.get("move_hits", 1)}


def render_state(state: VisibleState, battle_goal: str | None = None, unsupported: list[str] | None = None) -> str:
    """把可见状态整理成给模型看的 JSON。只取规划出牌用得到的字段。"""
    game, combat = state.game, state.combat or {}
    player = combat.get("player", {})
    view = {
        "character": game.get("class"),
        "act": game.get("act"),
        "floor": game.get("floor"),
        "room_type": game.get("room_type"),
        "turn": combat.get("turn"),
        "player": {
            "hp": player.get("current_hp"),
            "max_hp": player.get("max_hp"),
            "block": player.get("block"),
            "energy": player.get("energy"),
            "powers": _powers(player.get("powers", [])),
        },
        "hand": [
            {
                "card": _card_ref(c),
                "name": c.get("name"),
                "cost": c.get("cost"),
                "type": c.get("type"),
                "needs_target": c.get("has_target"),
                "playable": c.get("is_playable"),
            }
            for c in combat.get("hand", [])
        ],
        "draw_pile": _pile(combat.get("draw_pile", [])),
        "discard_pile": _pile(combat.get("discard_pile", [])),
        "exhaust_pile": _pile(combat.get("exhaust_pile", [])),
        "monsters": [
            {
                "index": i,
                "id": m.get("id"),
                "name": m.get("name"),
                "hp": m.get("current_hp"),
                "max_hp": m.get("max_hp"),
                "block": m.get("block"),
                "gone": bool(m.get("is_gone")),
                "intent": m.get("intent"),
                "attack": _attack(m),
                "powers": _powers(m.get("powers", [])),
            }
            for i, m in enumerate(combat.get("monsters", []))
        ],
        "relics": [{"id": r.get("id"), "counter": r.get("counter")} for r in game.get("relics", [])],
        "potions": [p.get("id") for p in game.get("potions", []) if p.get("id") != "Potion Slot"],
        "unsupported_cards": unsupported or [],
        "battle_goal": battle_goal,
    }
    return json.dumps(view, ensure_ascii=False)


def _to_plays(raw: Any) -> list[Play]:
    plays = []
    for item in raw:
        target = item.get("target")
        if not isinstance(item.get("card"), str) or not (target is None or isinstance(target, int)):
            raise ValueError("plays 里每一项要有字符串 card 和整数或 null 的 target")
        plays.append(Play(item["card"], target))
    return plays


class CombatAdvisor:
    def __init__(self, model: Model, check_lethal: bool = True):
        self.model = model
        self.check_lethal = check_lethal

    # ---------- 工具执行 ----------

    def _run_tool(self, state: VisibleState, call: ToolCall) -> ToolResult:
        """执行 settle、draw_odds 或 enemy_info。出错也要把原因告诉模型，让它调整。"""
        if call.args is None:
            return ToolResult(call.id, call.error or "参数缺失", is_error=True)
        try:
            if call.name == "settle":
                result = settle(state, _to_plays(call.args["plays"]))
                return ToolResult(call.id, json.dumps(asdict(result), ensure_ascii=False))
            if call.name == "draw_odds":
                combat = state.combat or {}
                p = draw_probability(
                    [_card_ref(c) for c in combat.get("draw_pile", [])],
                    set(call.args["cards"]),
                    draws=int(call.args["draws"]),
                    at_least=int(call.args["at_least"]),
                    discard_pile=[_card_ref(c) for c in combat.get("discard_pile", [])],
                )
                return ToolResult(call.id, json.dumps({"probability": round(p, 4)}))
            if call.name == "enemy_info":
                entry = monsters.lookup(str(call.args["monster_id"]))
                if entry is None:
                    # 查不到不算出错：如实告诉模型没有资料
                    return ToolResult(
                        call.id,
                        json.dumps(
                            {"found": False, "note": "没有收录这个敌人。不要凭印象断言它之后的招式。"},
                            ensure_ascii=False,
                        ),
                    )
                return ToolResult(call.id, json.dumps({"found": True, **entry}, ensure_ascii=False))
            return ToolResult(call.id, f"没有名为 {call.name} 的工具", is_error=True)
        except (KeyError, TypeError, ValueError, AttributeError) as e:
            return ToolResult(call.id, f"工具参数不对：{e}", is_error=True)

    # ---------- 核对 ----------

    def _check(
        self, state: VisibleState, plan: Any, lethal: list[Play] | None, lethal_flagged: bool
    ) -> tuple[str | None, SettleResult | None, bool]:
        """核对模型提交的计划。返回 (要退回的原因或 None, 结算结果, 这次是否提了斩杀)。"""
        try:
            plays = _to_plays(plan["plays"])
        except (KeyError, TypeError, ValueError, AttributeError) as e:
            return f"计划的格式不对：{e}。请按约定的字段重新提交。", None, False

        result = settle(state, plays)
        if not result.ok:
            return f"你的计划不合法。{result.reason}。请修正后重新提交完整计划。", result, False

        # 漏斩杀：存在本回合打死全部敌人的出牌，而计划没有做到。只提一次；
        # 模型说明理由后坚持原计划的，接受。
        if lethal and not lethal_flagged and not all_enemies_dead(result):
            line = "，".join(p.card if p.target is None else f"{p.card}→{p.target}" for p in lethal)
            return (
                f"本回合存在能打死全部敌人的出牌：{line}。你的计划没有做到。"
                "如果是有意不这样打，请保持计划并在 reasons 里说明原因；否则请改用能打死的打法。",
                result,
                True,
            )
        return None, result, False

    def _lethal_line(self, state: VisibleState) -> list[Play] | None:
        """单回合枚举出的打法如果能打死全部敌人，返回它。"""
        plays = best_single_turn(state)
        return plays if plays and all_enemies_dead(settle(state, plays)) else None

    # ---------- 降级 ----------

    def _fallback(self, state: VisibleState, why: str, **stats: Any) -> CombatAdvice:
        """模型用不了或计划始终过不了核对时，只展示程序算出的单回合结果。"""
        try:
            plays = best_single_turn(state)
            result = settle(state, plays)
        except SettleUnavailable as e:
            return CombatAdvice(source="none", note=f"{why}；结算器也不可用：{e}", **stats)
        return CombatAdvice(
            source="enumeration",
            plays=plays,
            summary="以下是只看本回合时程序算出的打法，没有考虑之后几回合。",
            result=result,
            note=why,
            **stats,
        )

    # ---------- 主流程 ----------

    def advise(self, state: VisibleState, battle_goal: str | None = None) -> CombatAdvice:
        if state.decision != Decision.COMBAT_TURN:
            raise ValueError("战斗顾问只处理战斗中轮到玩家出牌的状态")

        tier = pick_tier(state)
        try:
            unsupported = settle(state, []).unsupported_cards
            lethal = self._lethal_line(state) if self.check_lethal else None
        except SettleUnavailable as e:
            return CombatAdvice(source="none", tier=tier, note=f"结算器不可用：{e}")

        lethal_flagged = False

        def check(plan: Any) -> tuple[str | None, Any]:
            nonlocal lethal_flagged
            problem, result, flagged = self._check(state, plan, lethal, lethal_flagged)
            lethal_flagged = lethal_flagged or flagged
            return problem, result

        outcome = loop.run(
            model=self.model,
            tier=tier,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            first_message=render_state(state, battle_goal, unsupported),
            submit_tool="submit_plan",
            run_tool=lambda call: self._run_tool(state, call),
            check=check,
        )
        if not outcome.accepted:
            note = outcome.note.replace("答案没有通过核对", "计划没有通过核对")
            return self._fallback(state, note, tier=tier, **outcome.stats)

        plan = outcome.submitted
        return CombatAdvice(
            source="model",
            plays=_to_plays(plan["plays"]),
            tentative_from=plan.get("tentative_from"),
            summary=str(plan.get("summary", "")),
            reasons=list(plan.get("reasons", [])),
            risks=list(plan.get("risks", [])),
            uncertain=list(plan.get("uncertain", [])),
            result=outcome.payload,
            tier=tier,
            **outcome.stats,
        )
