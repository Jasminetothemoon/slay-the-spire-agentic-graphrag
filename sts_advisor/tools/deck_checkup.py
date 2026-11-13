"""计算工具：牌组体检。

回答「这副牌现在缺什么」和「加入某张牌之后会变成什么样」。给构筑顾问用。

8 项能力里，能算的用程序算，算不了的只列出候选，交给构筑顾问判断
（docs/v2_design.md 改动点 6）：

    算的：前期伤害、群伤、前期格挡、过牌、能量
    估的：成长伤害、成长格挡、回复 —— 这里只列出相关的牌和遗物

「算的」怎么算：把牌组里可能出现的一手牌逐一交给结算模块，
枚举这一手所有的出牌顺序，取能打出的最大伤害和最大格挡，再按出现的可能性加权平均。
牌组不大时穷举所有的手牌组合，结果是精确的；牌组大了改为固定种子的抽样。

一手几张牌、每回合几点能量不是写死的：默认 5 张、3 点，会按持有的遗物调整（见 turn_shape.py）。
第一回合和之后的回合不一样时（例如蛇戒让第一回合多抽 2 张），第一回合单独算一份。

已知的局限：
- 只看单独的一回合。跨回合才见效的东西不计入：毒、能力牌的后续收益、成长。
- 抽到的牌用占位牌代替，所以抽牌牌带来的额外输出不计入伤害和格挡，单独记在「过牌」里。
- 最大伤害和最大格挡是分别取的，同一手牌不能同时达到两者。
- 不考虑开场就生效的其他遗物效果（例如开场加力量），也不考虑固有牌。
- 按条件触发的能量和抽牌遗物没有计入，影响大的会写在结果的 assumptions 里。
- 结算模块不认识的牌当作打不出的废牌，并在结果里列出。
"""
from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import asdict, dataclass, field
from itertools import combinations
from typing import Any

from sts_advisor.ingest.visible_state import VisibleState
from sts_advisor.knowledge import monsters, trials
from sts_advisor.tools.settle import RELIC_ID_TO_BOTTLED_NAME, _bottled
from sts_advisor.tools.turn_shape import TurnShape, turn_shape

DUMMY_HP = 100_000  # 打不死的靶子，用掉了多少血就是打出了多少伤害
AOE_TARGETS = 3
EXACT_LIMIT = 800  # 手牌组合数不超过这个值时穷举（12 张牌取 5 张是 792 种），否则抽样
SAMPLES = 400
MAX_PATHS = 1500  # 单手牌枚举出牌顺序的上限
SKIP = "跳过"


def card_ref(card: dict[str, Any]) -> str:
    return card.get("id", "") + "+" * int(card.get("upgrades", 0))


@dataclass
class Checkup:
    deck_size: int
    method: str  # "exact"：穷举了所有手牌组合；"sampled"：抽样
    hands: int  # 参与计算的手牌数（穷举时是组合总数，抽样时是样本数）
    energy: int  # 按遗物推出的每回合能量
    hand_size: int  # 按遗物推出的每回合抽牌数
    first_turn_energy: int
    first_turn_hand_size: int
    # ---- 算的 ----
    avg_damage: float  # 一手牌单回合对单个目标能打出的最大伤害，平均值
    low_damage: float  # 手气较差时（最差的五分之一）的水平
    avg_aoe_damage: float  # 面对 3 个目标时，单回合能打出的最大总伤害，平均值
    aoe_bonus: float  # avg_aoe_damage 比 avg_damage 多出的部分；0 表示没有任何群伤
    avg_block: float  # 一手牌单回合能叠出的最大格挡，平均值
    low_block: float
    first_turn_damage: float  # 第一回合的平均最大伤害；第一回合和平时一样时等于 avg_damage
    first_turn_block: float
    draw_per_turn: float  # 平均每手牌里，带来的额外抽牌数
    avg_cost: float  # 能打出的牌的平均费用
    expensive_share: float  # 2 费及以上的牌占比
    skill_share: float  # 技能牌占比
    chance_to_see_a_card: float  # 任意指定的一张牌出现在一手牌里的概率
    energy_cards: list[str] = field(default_factory=list)  # 能给能量的牌
    dead_cards: list[str] = field(default_factory=list)  # 打不出的牌：诅咒、状态
    unsupported_cards: list[str] = field(default_factory=list)  # 结算模块不认识、因此被当成废牌的
    assumptions: list[str] = field(default_factory=list)  # 没有计入、会影响准确度的事项
    # ---- 估的：只列候选，由构筑顾问判断够不够 ----
    power_cards: list[str] = field(default_factory=list)  # 能力牌：打出后持续生效，多数成长来自这里
    healing_cards: list[str] = field(default_factory=list)  # 带回复效果的牌
    relics: list[str] = field(default_factory=list)  # 遗物原样列出，成长和回复类遗物由顾问识别


@dataclass
class Comparison:
    candidate: str  # 候选牌的编号，或「跳过」
    checkup: Checkup
    delta: dict[str, float]  # 相对当前牌组的变化


DELTA_FIELDS = (
    "avg_damage",
    "low_damage",
    "avg_aoe_damage",
    "aoe_bonus",
    "avg_block",
    "low_block",
    "first_turn_damage",
    "first_turn_block",
    "draw_per_turn",
    "avg_cost",
    "chance_to_see_a_card",
)


Row = tuple[int, int, int]  # 一手牌的（伤害，对 3 个目标的总伤害，格挡）


def _weighted_low(values: list[tuple[float, float]], share: float = 0.2) -> float:
    """最差的那一部分（按出现的可能性算，默认五分之一）的平均值。"""
    total = sum(w for _, w in values)
    if total <= 0:
        return 0.0
    budget = total * share
    acc = used = 0.0
    for value, weight in sorted(values):
        take = min(weight, budget - used)
        if take <= 0:
            break
        acc += value * take
        used += take
    return acc / used if used else 0.0


class DeckChecker:
    """一次体检会用到同一套遗物和能量。同一个实例里，算过的手牌会被记住，
    比较多个候选时大部分手牌不用重算。"""

    def __init__(self, relics: list[dict[str, Any]] | None = None, shape: TurnShape | None = None, seed: int = 0):
        self.relics_raw = relics or []
        self.shape = shape or turn_shape(self.relics_raw)
        self.seed = seed
        self._hand_cache: dict[tuple[tuple[str, ...], int, int], tuple[int, int]] = {}
        self._card_cache: dict[str, Any] = {}

        CardId, _, _, _, _, MemoryBook = _bottled()
        from rs.calculator.battle_state import BattleState
        from rs.calculator.card_effects import get_card_effects
        from rs.calculator.game_state_converter import make_card, make_relic_id
        from rs.calculator.interfaces.card_effects_interface import TargetType
        from rs.calculator.monster import Monster
        from rs.calculator.play_path import get_paths_bfs
        from rs.calculator.player import Player
        from rs.game.card import Card as GameCard

        self._b = dict(
            CardId=CardId,
            MemoryBook=MemoryBook,
            BattleState=BattleState,
            get_card_effects=get_card_effects,
            make_card=make_card,
            TargetType=TargetType,
            Monster=Monster,
            get_paths_bfs=get_paths_bfs,
            Player=Player,
            GameCard=GameCard,
        )
        self._relics = {
            make_relic_id(RELIC_ID_TO_BOTTLED_NAME.get(r.get("id", ""), r.get("id", "")).lower()): r.get("counter", -1)
            for r in self.relics_raw
        }

    # ---------- 单张牌 ----------

    def _card(self, raw: dict[str, Any]) -> Any:
        """把游戏状态里的一张牌转成结算模块的牌。同名同升级的牌共用一个对象。"""
        ref = card_ref(raw)
        if ref not in self._card_cache:
            self._card_cache[ref] = self._b["make_card"](self._b["GameCard"](raw))
        return self._card_cache[ref]

    def _player(self, energy: int | None = None) -> Any:
        energy = self.shape.energy if energy is None else energy
        return self._b["Player"](True, 80, 80, 0, {}, energy=energy, relics=self._relics, potions=[])

    def _effects(self, raw: dict[str, Any]) -> list[Any]:
        try:
            return list(self._b["get_card_effects"](self._card(raw), self._player(), [], [], []))
        except Exception:  # 结算模块对个别牌需要完整的局面才能给出效果，拿不到就当没有
            return []

    def _is_aoe(self, raw: dict[str, Any]) -> bool:
        wide = (self._b["TargetType"].ALL_MONSTERS, self._b["TargetType"].RANDOM)
        return any(e.target in wide for e in self._effects(raw))

    # ---------- 一手牌 ----------

    def _evaluate_hand(
        self, hand: list[dict[str, Any]], rest: list[dict[str, Any]], targets: int, energy: int
    ) -> tuple[int, int]:
        """这一手牌单回合能打出的最大伤害和最大格挡。"""
        key = (tuple(sorted(card_ref(c) for c in hand)), targets, energy)
        if key in self._hand_cache:
            return self._hand_cache[key]

        b = self._b
        book = b["MemoryBook"].new_default()
        state = b["BattleState"](
            player=self._player(energy),
            hand=[self._card(c) for c in hand],
            draw_pile=[self._card(c) for c in rest],
            monsters=[b["Monster"](False, DUMMY_HP, DUMMY_HP, 0, {}) for _ in range(targets)],
            relics=self._relics,
            potions=[],
            memory_by_card=book.memory_by_card.copy(),
            memory_general=book.memory_general.copy(),
        )
        best_damage = best_block = 0
        for path in b["get_paths_bfs"](state, MAX_PATHS).values():
            damage = sum(DUMMY_HP - m.current_hp for m in path.state.monsters)
            best_damage = max(best_damage, damage)
            best_block = max(best_block, path.state.player.block)
        self._hand_cache[key] = (best_damage, best_block)
        return best_damage, best_block

    def _hands(self, n: int, size: int) -> tuple[str, list[tuple[int, ...]]]:
        """从 n 张牌里取 size 张的各种取法（用牌组下标表示）。取法不多时穷举，否则固定种子抽样。"""
        if math.comb(n, size) <= EXACT_LIMIT:
            return "exact", list(combinations(range(n), size))
        rng = random.Random(self.seed)
        return "sampled", [tuple(sorted(rng.sample(range(n), size))) for _ in range(SAMPLES)]

    def _rows(
        self, deck: list[dict[str, Any]], hand_size: int, energy: int, forced: dict[str, Any] | None = None
    ) -> tuple[str, list[Row]]:
        """逐手计算。forced 不为空时，每一手都包含这张牌，其余从 deck 里取。
        返回 (方法, 每一手的 (伤害, 群伤总伤害, 格挡))，各手等权。"""
        n = len(deck)
        size = min(hand_size - (1 if forced else 0), n)
        method, picks = self._hands(n, size)
        aoe_capable = [self._is_aoe(c) for c in deck]
        forced_aoe = bool(forced) and self._is_aoe(forced)

        rows: list[Row] = []
        for idx in picks:
            chosen = set(idx)
            hand = [deck[i] for i in idx] + ([forced] if forced else [])
            rest = [deck[i] for i in range(n) if i not in chosen]
            damage, block = self._evaluate_hand(hand, rest, 1, energy)
            # 手里没有能打到多个目标的牌时，对 3 个目标的总伤害和对 1 个目标一样，不用再算
            has_aoe = forced_aoe or any(aoe_capable[i] for i in idx)
            aoe = self._evaluate_hand(hand, rest, AOE_TARGETS, energy)[0] if has_aoe else damage
            rows.append((damage, aoe, block))
        return method, rows

    def _weighted(
        self, deck: list[dict[str, Any]], hand_size: int, energy: int, candidate: dict[str, Any] | None
    ) -> tuple[str, int, list[tuple[Row, float]]]:
        """deck（可选地再加一张 candidate）在给定手牌张数和能量下的各手结果和权重。

        加入一张牌之后，一手牌要么不含它（和原来的手牌一模一样），要么含它。
        所以只需要另算「含它」的那部分，再按它上手的概率和原来的结果加权。
        这样加牌前后共用同一批手牌，牌组大到要抽样时，差值也不会被抽样的波动盖住。"""
        n = len(deck)
        method, rows = self._rows(deck, hand_size, energy)
        if candidate is None:
            return method, len(rows), [(row, 1.0 / len(rows)) for row in rows]
        if n < hand_size:
            # 牌比一手还少：加进来就一定上手
            method, rows = self._rows(deck + [candidate], hand_size, energy)
            return method, len(rows), [(row, 1.0 / len(rows)) for row in rows]
        with_method, with_rows = self._rows(deck, hand_size, energy, forced=candidate)
        p = hand_size / (n + 1)  # 新牌出现在一手牌里的概率
        weighted = [(row, (1 - p) / len(rows)) for row in rows]
        weighted += [(row, p / len(with_rows)) for row in with_rows]
        both_exact = method == with_method == "exact"
        return ("exact" if both_exact else "sampled"), len(rows) + len(with_rows), weighted

    def _checkup(self, deck: list[dict[str, Any]], candidate: dict[str, Any] | None) -> Checkup:
        """deck（可选地再加一张 candidate）的体检。"""
        shape = self.shape
        method, hands, weighted = self._weighted(deck, shape.hand_size, shape.energy, candidate)
        column = lambda rows, i: [(row[i], w) for row, w in rows]  # noqa: E731
        avg = lambda rows, i: sum(row[i] * w for row, w in rows)  # noqa: E731

        if shape.first_turn_differs:
            first_method, _, first = self._weighted(deck, shape.first_turn_hand_size, shape.first_turn_energy, candidate)
            method = method if first_method == "exact" else "sampled"
        else:
            first = weighted

        full = deck + ([candidate] if candidate else [])
        n = len(full)
        hand = min(shape.hand_size, n)
        fake = self._b["CardId"].FAKE
        refs = [card_ref(c) for c in full]
        draws = [sum(e.draw for e in self._effects(c)) for c in full]
        playable_costs = [c["cost"] for c in full if isinstance(c.get("cost"), int) and c["cost"] >= 0]

        avg_damage, avg_aoe = avg(weighted, 0), avg(weighted, 1)
        return Checkup(
            deck_size=n,
            method=method,
            hands=hands,
            energy=shape.energy,
            hand_size=shape.hand_size,
            first_turn_energy=shape.first_turn_energy,
            first_turn_hand_size=shape.first_turn_hand_size,
            avg_damage=round(avg_damage, 2),
            low_damage=round(_weighted_low(column(weighted, 0)), 2),
            avg_aoe_damage=round(avg_aoe, 2),
            aoe_bonus=round(avg_aoe - avg_damage, 2),
            avg_block=round(avg(weighted, 2), 2),
            low_block=round(_weighted_low(column(weighted, 2)), 2),
            first_turn_damage=round(avg(first, 0), 2),
            first_turn_block=round(avg(first, 2), 2),
            draw_per_turn=round(sum(draws) / n * hand, 2),
            avg_cost=round(sum(playable_costs) / len(playable_costs), 2) if playable_costs else 0.0,
            expensive_share=round(sum(1 for c in playable_costs if c >= 2) / n, 2),
            skill_share=round(sum(1 for c in full if c.get("type") == "SKILL") / n, 2),
            chance_to_see_a_card=round(hand / n, 3),
            energy_cards=sorted({r for r, c in zip(refs, full) if any(e.energy_gain > 0 for e in self._effects(c))}),
            dead_cards=sorted({r for r, c in zip(refs, full) if c.get("type") in ("CURSE", "STATUS")}),
            unsupported_cards=sorted({r for r, c in zip(refs, full) if self._card(c).id == fake}),
            assumptions=list(shape.notes),
            power_cards=sorted({r for r, c in zip(refs, full) if c.get("type") == "POWER"}),
            healing_cards=sorted({r for r, c in zip(refs, full) if any(e.heal > 0 for e in self._effects(c))}),
            relics=[r.get("id", "") for r in self.relics_raw],
        )

    # ---------- 整副牌 ----------

    def checkup(self, deck: list[dict[str, Any]]) -> Checkup:
        if not deck:
            raise ValueError("牌组是空的")
        return self._checkup(deck, None)

    def compare(self, deck: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> list[Comparison]:
        """当前牌组分别加入每张候选牌之后的体检，以及相对现在的变化。「跳过」是一个正式的候选。"""
        base = self.checkup(deck)
        base_values = asdict(base)
        out = [Comparison(SKIP, base, {k: 0.0 for k in DELTA_FIELDS})]
        for candidate in candidates:
            after = self._checkup(deck, candidate)
            values = asdict(after)
            out.append(
                Comparison(card_ref(candidate), after, {k: round(values[k] - base_values[k], 3) for k in DELTA_FIELDS})
            )
        return out


# ---------- 对着游戏状态用 ----------


def checkup_state(state: VisibleState) -> Checkup:
    game = state.game
    return DeckChecker(game.get("relics", [])).checkup(game.get("deck", []))


def compare_candidates(state: VisibleState, candidates: list[dict[str, Any]]) -> list[Comparison]:
    game = state.game
    return DeckChecker(game.get("relics", [])).compare(game.get("deck", []), candidates)


def trials_for(state: VisibleState, checkup: Checkup) -> list[dict[str, Any]]:
    """这一幕要过的考验，以及按体检结果粗略估算打死每个敌人要几回合。

    估算很粗：只用平均每回合的伤害去除敌人的血量，不计敌人的格挡和成长，也不计你的抽牌和成长。
    它是给构筑顾问参考的数量级，不是预测。"""
    game = state.game
    entries = list(trials.for_act(game.get("act", 1)))
    boss = monsters.lookup_by_name(str(game.get("act_boss", "")))
    if boss is not None:
        entries.append({"monster_id": boss["id"], "count": 1, "metric": "avg_damage", "needs": "本幕 Boss，机制见招式表"})

    out = []
    for entry in entries:
        info = monsters.lookup(entry["monster_id"])
        if info is None:
            continue
        hp = sum(info["hp"]) / 2 * entry["count"]
        per_turn = getattr(checkup, entry["metric"])
        out.append(
            {
                "monster_id": entry["monster_id"],
                "name_zh": info["name_zh"],
                "kind": info["kind"],
                "count": entry["count"],
                "total_hp": round(hp),
                "needs": entry["needs"],
                "damage_per_turn": per_turn,
                "rough_turns_to_kill": math.ceil(hp / per_turn) if per_turn > 0 else None,
                "warnings": info["warnings"],
            }
        )
    return out
