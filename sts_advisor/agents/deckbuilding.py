"""构筑顾问：战斗后三选一（或跳过）时，建议拿哪张牌。

分工（docs/v2_design.md 改动点 6、8、9）：
- 程序先做牌组体检：现在的牌组各项能力是多少，加入每张候选牌之后各变多少，眼前的考验要打几回合。
- 模型在这些数字上做取舍，并且必须同时回答「会不会太贪」和「会不会太怂」。
- 模型的理由如果引用了体检的某项指标，要写明是哪一项、往哪个方向变。程序拿体检的结果核对，
  说反了就退回去。
- 体检算不了的东西（能力牌的长期收益、成长、毒、抽牌带来的输出）靠模型判断，这类理由标为「未核对」。

目前只处理抓牌。篝火、商店、Boss 遗物还没有做。
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
from sts_advisor.tools.deck_checkup import DELTA_FIELDS, SKIP, Comparison, DeckChecker, card_ref, trials_for
from sts_advisor.tools.settle import SettleUnavailable

TIER = "strong"  # 抓牌不赶时间，用强的档位
CLAIMS = ("increase", "decrease", "no_change")
NO_CHANGE_TOLERANCE = 0.005

METRIC_NOTES = {
    "avg_damage": "一手牌单回合对单个目标能打出的最大伤害，平均值",
    "low_damage": "手气较差时（最差的五分之一）的单回合伤害",
    "avg_aoe_damage": "面对 3 个目标时，单回合能打出的最大总伤害，平均值",
    "aoe_bonus": "群伤带来的额外伤害；0 表示牌组里没有任何群伤",
    "avg_block": "一手牌单回合能叠出的最大格挡，平均值",
    "low_block": "手气较差时的单回合格挡",
    "first_turn_damage": "第一回合的平均最大伤害（有些遗物让第一回合多抽牌或多能量）",
    "first_turn_block": "第一回合的平均最大格挡",
    "draw_per_turn": "平均每手牌里带来的额外抽牌数",
    "avg_cost": "能打出的牌的平均费用",
    "chance_to_see_a_card": "任意指定的一张牌出现在一手牌里的概率；牌组越厚越低",
}

SYSTEM_PROMPT = """你是《杀戮尖塔》的构筑顾问。玩家是新手，刚打完一场战斗，要从几张牌里选一张加入牌组，也可以跳过。你的任务是建议怎么选，并用新手听得懂的话说明为什么。

你会收到一份 JSON：
- 玩家的角色、所在的幕和层、血量、遗物、现在的牌组、本幕的 Boss。
- options：这次可以选的每一项。「跳过」在列表里时，它和其他选项地位相同。
- checkup_now：程序对现在这副牌做的体检。各项指标的含义在 metric_notes 里。
- change_if_taken：加入每张候选牌之后，各项指标相对现在的变化。
- trials：这一幕里最考验牌组的敌人，以及按现在的牌组和拿了每张候选牌之后，粗略估算打死它要几回合。

体检的数字是程序算的，可以直接信。但它只看单独的一回合，下面这些它算不出来，要靠你判断：
- 能力牌和其他成长手段的收益在之后的回合，体检里它们常常是负的。
- 抽牌带来的额外输出没有计入伤害和格挡，只记在 draw_per_turn 里。
- 毒这类延迟伤害没有计入。
- checkup_now 的 unsupported_cards 和候选里程序不认识的牌，被当成了废牌。
- 「打死要几回合」只是血量除以平均伤害，是数量级，不是预测。

怎么取舍：
- 先看眼前要过的考验。牌组在哪一项上过不去，就优先补那一项；补到够用就可以了，不必一直堆。
- 每加一张牌，其他牌都会更难上手。候选牌都补不上缺口、也没有明显的长期价值时，跳过是正当的选择。
- 两个方向都要检查，并分别写出结论：
  - 会不会太贪：是不是为了以后才见效的东西，放着眼前过不去的考验不管。
  - 会不会太怂：是不是只顾眼前的数字，或者只是怕牌组变厚，就放弃了明显值得拿的牌。

工具：
- enemy_info：按敌人的 id 查它的招式和要注意的机制。想确认某个考验或 Boss 具体考验什么时使用。查不到的敌人不要凭印象断言。
- submit_choice：提交你的建议。每次回答都要以调用它结束。

submit_choice 的各字段：
- choice：你建议的选项，必须是 options 里的一项。
- ranking：所有选项从最推荐到最不推荐的完整排序，第一项就是 choice。
- summary：一句话结论。
- reasons：两到四条理由。每条理由：
  - text：写给新手看的说明。不要自己报具体数字，数字由程序附上。
  - metric 和 claim：这条理由如果依据的是体检的某项指标，就填指标名和变化方向（increase、decrease、no_change），说的是「选了 choice 之后，这项指标相对现在怎么变」。程序会拿体检的结果核对，方向说反了会被退回。
  - 这条理由如果是你自己的判断（例如能力牌的长期收益），metric 和 claim 都填 null。
- too_greedy：对「会不会太贪」的回答。
- too_timid：对「会不会太怂」的回答。
- risks：这样选的代价，没有就留空数组。
- uncertain：你没把握的地方，没有就留空数组。"""

ENEMY_INFO_TOOL = ToolSpec(
    name="enemy_info",
    description=(
        "查一个敌人的资料：招式和数值、出招规则、要特别注意的机制。"
        "想确认某个考验或本幕 Boss 具体考验牌组的什么时调用。没有收录的敌人会明确告诉你查不到。"
    ),
    parameters={
        "type": "object",
        "properties": {"monster_id": {"type": "string", "description": "敌人的 id，取自输入里 trials[].monster_id"}},
        "required": ["monster_id"],
        "additionalProperties": False,
    },
)

SUBMIT_TOOL = ToolSpec(
    name="submit_choice",
    description="提交抓牌建议。想清楚之后调用，每次回答都以它结束。没通过核对时原因会退回来。",
    parameters={
        "type": "object",
        "properties": {
            "choice": {"type": "string", "description": "建议的选项，必须是 options 里的一项"},
            "ranking": {
                "type": "array",
                "items": {"type": "string"},
                "description": "所有选项从最推荐到最不推荐的完整排序，第一项是 choice",
            },
            "summary": {"type": "string", "description": "一句话结论"},
            "reasons": {
                "type": "array",
                "description": "两到四条理由",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "写给新手的说明，不含具体数字"},
                        "metric": {
                            "anyOf": [{"type": "string", "enum": list(DELTA_FIELDS)}, {"type": "null"}],
                            "description": "依据的体检指标；是自己的判断时填 null",
                        },
                        "claim": {
                            "anyOf": [{"type": "string", "enum": list(CLAIMS)}, {"type": "null"}],
                            "description": "选了 choice 之后这项指标怎么变；metric 为 null 时也填 null",
                        },
                    },
                    "required": ["text", "metric", "claim"],
                    "additionalProperties": False,
                },
            },
            "too_greedy": {"type": "string", "description": "这样选会不会太贪"},
            "too_timid": {"type": "string", "description": "这样选会不会太怂"},
            "risks": {"type": "array", "items": {"type": "string"}},
            "uncertain": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["choice", "ranking", "summary", "reasons", "too_greedy", "too_timid", "risks", "uncertain"],
        "additionalProperties": False,
    },
)

TOOLS = [ENEMY_INFO_TOOL, SUBMIT_TOOL]


@dataclass
class Reason:
    text: str
    metric: str | None = None
    claim: str | None = None
    change: float | None = None  # 体检算出的实际变化；只有引用了指标的理由才有
    checked: bool = False  # True：方向经程序核对属实；False：是模型自己的判断，没有核对


@dataclass
class DeckAdvice:
    source: str  # "model"：建议通过了核对；"checkup_only"：降级，只给体检结果；"none"：连体检也做不了
    options: list[str] = field(default_factory=list)
    choice: str | None = None
    ranking: list[str] = field(default_factory=list)
    summary: str = ""
    reasons: list[Reason] = field(default_factory=list)
    too_greedy: str = ""
    too_timid: str = ""
    risks: list[str] = field(default_factory=list)
    uncertain: list[str] = field(default_factory=list)
    checkup_now: dict[str, Any] = field(default_factory=dict)
    change_if_taken: dict[str, dict[str, float]] = field(default_factory=dict)
    trials: list[dict[str, Any]] = field(default_factory=list)
    tier: str = TIER
    model_calls: int = 0
    tool_calls: int = 0
    pushbacks: int = 0
    note: str = ""


@dataclass
class _Facts:
    """一次抓牌里程序算出来的全部事实。"""

    options: list[str]
    comparisons: dict[str, Comparison]
    trials: list[dict[str, Any]]

    @property
    def change_if_taken(self) -> dict[str, dict[str, float]]:
        return {name: dict(c.delta) for name, c in self.comparisons.items()}

    @property
    def checkup_now(self) -> dict[str, Any]:
        return asdict(self.comparisons[SKIP].checkup)


def _gather(state: VisibleState) -> _Facts:
    game = state.game
    screen = game.get("screen_state", {})
    cards = list(screen.get("cards", []))
    rows = DeckChecker(game.get("relics", [])).compare(game.get("deck", []), cards)
    comparisons = {row.candidate: row for row in rows}

    options = [card_ref(c) for c in cards]
    if screen.get("skip_available", True):
        options.append(SKIP)

    # 每个考验：按现在的牌组，以及拿了每张候选牌之后，各要打几回合
    trial_rows = trials_for(state, comparisons[SKIP].checkup)
    for row in trial_rows:
        row["rough_turns_if_taken"] = {}
    for name, comparison in comparisons.items():
        if name == SKIP:
            continue
        for row, after in zip(trial_rows, trials_for(state, comparison.checkup)):
            row["rough_turns_if_taken"][name] = after["rough_turns_to_kill"]
    return _Facts(options, comparisons, trial_rows)


def render_state(state: VisibleState, facts: _Facts) -> str:
    game = state.game
    screen = game.get("screen_state", {})
    by_ref = {card_ref(c): c for c in screen.get("cards", [])}
    options = []
    for name in facts.options:
        if name == SKIP:
            note = "不拿牌"
            if screen.get("bowl_available"):
                note += "；持有唱歌碗，跳过会加 2 点最大生命"
            options.append({"option": SKIP, "note": note})
        else:
            c = by_ref[name]
            options.append(
                {"option": name, "name": c.get("name"), "type": c.get("type"), "cost": c.get("cost"), "rarity": c.get("rarity")}
            )
    view = {
        "character": game.get("class"),
        "act": game.get("act"),
        "floor": game.get("floor"),
        "hp": game.get("current_hp"),
        "max_hp": game.get("max_hp"),
        "gold": game.get("gold"),
        "act_boss": game.get("act_boss"),
        "relics": [r.get("id") for r in game.get("relics", [])],
        "deck": dict(sorted(Counter(card_ref(c) for c in game.get("deck", [])).items())),
        "options": options,
        "checkup_now": facts.checkup_now,
        "change_if_taken": {k: v for k, v in facts.change_if_taken.items() if k in facts.options},
        "trials": [{k: v for k, v in row.items() if k != "warnings"} for row in facts.trials],
        "metric_notes": METRIC_NOTES,
    }
    return json.dumps(view, ensure_ascii=False)


class DeckAdvisor:
    def __init__(self, model: Model):
        self.model = model

    def _run_tool(self, call: ToolCall) -> ToolResult:
        if call.args is None:
            return ToolResult(call.id, call.error or "参数缺失", is_error=True)
        if call.name != "enemy_info":
            return ToolResult(call.id, f"没有名为 {call.name} 的工具", is_error=True)
        try:
            entry = monsters.lookup(str(call.args["monster_id"]))
        except (KeyError, TypeError) as e:
            return ToolResult(call.id, f"工具参数不对：{e}", is_error=True)
        if entry is None:
            # 查不到不算出错：如实告诉模型没有资料
            body = {"found": False, "note": "没有收录这个敌人。不要凭印象断言它的招式。"}
        else:
            body = {"found": True, **entry}
        return ToolResult(call.id, json.dumps(body, ensure_ascii=False))

    def _check(self, facts: _Facts, submitted: Any) -> tuple[str | None, list[Reason] | None]:
        """核对模型提交的建议。返回 (要退回的原因或 None, 核对过的理由)。"""
        if not isinstance(submitted, dict):
            return "提交的内容格式不对。请按约定的字段重新提交。", None
        options = facts.options
        choice, ranking = submitted.get("choice"), submitted.get("ranking")

        if choice not in options:
            return f"choice 必须是 options 里的一项：{options}。你给的是 {choice!r}。", None
        if not isinstance(ranking, list) or sorted(ranking) != sorted(options):
            return f"ranking 要把所有选项各列一次：{options}。", None
        if ranking[0] != choice:
            return "ranking 的第一项必须和 choice 相同。", None
        for key, label in (("too_greedy", "会不会太贪"), ("too_timid", "会不会太怂")):
            if not str(submitted.get(key, "")).strip():
                return f"{key} 不能为空。请回答这样选「{label}」。", None

        raw_reasons = submitted.get("reasons")
        if not isinstance(raw_reasons, list) or not raw_reasons:
            return "至少要给一条理由。", None

        delta = facts.comparisons[choice].delta
        reasons: list[Reason] = []
        for item in raw_reasons:
            if not isinstance(item, dict) or not str(item.get("text", "")).strip():
                return "每条理由都要有 text。", None
            metric, claim = item.get("metric"), item.get("claim")
            if metric is None and claim is None:
                reasons.append(Reason(text=item["text"]))  # 模型自己的判断，不核对
                continue
            if metric not in DELTA_FIELDS or claim not in CLAIMS:
                return (
                    f"理由「{item['text']}」的 metric 和 claim 要么都填、要么都是 null。"
                    f"metric 可选 {list(DELTA_FIELDS)}，claim 可选 {list(CLAIMS)}。"
                ), None
            change = delta[metric]
            actual = "no_change" if abs(change) < NO_CHANGE_TOLERANCE else ("increase" if change > 0 else "decrease")
            if claim != actual:
                return (
                    f"理由「{item['text']}」和体检对不上：你说选 {choice} 之后 {metric} 会 {claim}，"
                    f"但体检算出来的变化是 {change:+.2f}（{actual}）。请修正这条理由，或者重新考虑选择。"
                ), None
            reasons.append(Reason(text=item["text"], metric=metric, claim=claim, change=change, checked=True))
        return None, reasons

    def advise(self, state: VisibleState) -> DeckAdvice:
        if state.decision != Decision.CARD_REWARD:
            raise ValueError("构筑顾问目前只处理战斗后的抓牌")
        try:
            facts = _gather(state)
        except SettleUnavailable as e:
            return DeckAdvice(source="none", note=f"体检做不了：{e}")

        common = dict(
            options=facts.options,
            checkup_now=facts.checkup_now,
            change_if_taken={k: v for k, v in facts.change_if_taken.items() if k in facts.options},
            trials=facts.trials,
        )
        outcome = loop.run(
            model=self.model,
            tier=TIER,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            first_message=render_state(state, facts),
            submit_tool="submit_choice",
            run_tool=self._run_tool,
            check=lambda submitted: self._check(facts, submitted),
        )
        if not outcome.accepted:
            # 降级：只展示体检结果，不给模型的结论
            return DeckAdvice(
                source="checkup_only",
                summary="模型的建议没有拿到，以下只有程序算出的体检结果。",
                note=outcome.note.replace("答案没有通过核对", "建议没有通过核对"),
                **common,
                **outcome.stats,
            )
        s = outcome.submitted
        return DeckAdvice(
            source="model",
            choice=s["choice"],
            ranking=list(s["ranking"]),
            summary=str(s.get("summary", "")),
            reasons=outcome.payload,
            too_greedy=str(s["too_greedy"]),
            too_timid=str(s["too_timid"]),
            risks=list(s.get("risks", [])),
            uncertain=list(s.get("uncertain", [])),
            **common,
            **outcome.stats,
        )
