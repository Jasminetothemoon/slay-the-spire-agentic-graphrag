"""计算工具：结算器。

给一串出牌，算出打完之后的结果：敌人剩多少血、是否斩杀、自己的格挡、
敌人按本回合意图行动后自己掉多少血。出牌不合法时给出原因。

实现方式：包装开源项目 bottled_ai 的单回合计算模块
（https://github.com/xaved88/bottled_ai ，MIT 许可，作为子模块放在 third_party/bottled_ai）。
它只算当前回合，不模拟抽到什么牌。

已知的缺口（见 docs/v2_design.md「结算器验证记录」）：
- 它靠一份跨调用的记录知道本回合已打几张牌、当前姿态等。这里每次调用都用空白记录，
  所以依赖这些计数的牌和遗物可能算不准。接入层能逐步计数之后再接上。
- 它缺一部分牌和遗物。缺的牌会出现在结果的 unsupported_cards 里。
"""
from __future__ import annotations

import copy
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from sts_advisor.ingest.visible_state import VisibleState

BOTTLED_ROOT = Path(__file__).resolve().parents[2] / "third_party" / "bottled_ai"

# bottled_ai 按英文显示名识别遗物和药水。游戏状态里的内部编号绝大多数就是英文名；
# 个别不一致的在这里登记：内部编号 -> bottled_ai 认识的名字。发现一个补一个。
RELIC_ID_TO_BOTTLED_NAME: dict[str, str] = {}
POTION_ID_TO_BOTTLED_NAME: dict[str, str] = {}


class SettleUnavailable(RuntimeError):
    """子模块没有初始化，结算器用不了。"""


@dataclass(frozen=True)
class Play:
    """一次出牌。card 是游戏内部编号，升级过的在后面加 +，例如 "Bash+"。
    target 是敌人下标；不需要目标的牌填 None。"""

    card: str
    target: int | None = None


@dataclass
class SettleResult:
    ok: bool
    reason: str = ""  # ok 为 False 时：第几步、为什么不合法
    failed_step: int | None = None
    monsters_before: list[dict[str, Any]] = field(default_factory=list)
    monsters_after: list[dict[str, Any]] = field(default_factory=list)  # 打完牌之后、敌人行动之前
    killed: list[int] = field(default_factory=list)  # 被这串出牌打死的敌人下标
    block_after: int = 0
    energy_left: int = 0
    hand_after: list[str] = field(default_factory=list)
    hp_lost_after_enemy_turn: int = 0  # 敌人按本回合意图行动之后，自己掉了多少血
    unsupported_cards: list[str] = field(default_factory=list)  # 手牌里结算器不认识的牌
    unrecognized_relics: list[str] = field(default_factory=list)  # 结算器不认识的遗物，结果可能不准


def _bottled():
    """延迟导入 bottled_ai 的模块。"""
    if not (BOTTLED_ROOT / "rs" / "calculator").is_dir():
        raise SettleUnavailable(
            "没有找到 third_party/bottled_ai。先运行：git submodule update --init third_party/bottled_ai"
        )
    root = str(BOTTLED_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    from rs.calculator.enums.card_id import CardId
    from rs.calculator.enums.relic_id import RelicId
    from rs.calculator.game_state_converter import battlestate_deepcopy, create_battle_state
    from rs.machine.state import GameState
    from rs.machine.the_bots_memory_book import TheBotsMemoryBook

    return CardId, RelicId, create_battle_state, battlestate_deepcopy, GameState, TheBotsMemoryBook


def _label(card_id: str, upgrades: int) -> str:
    return card_id.lower() + "+" * upgrades


def _prepare(data: dict[str, Any]) -> dict[str, Any]:
    """把状态改成 bottled_ai 认得的样子：遗物和药水的显示名换成内部编号对应的英文名。
    中文客户端下显示名是中文，不换就全部认不出。"""
    d = copy.deepcopy(data)
    game = d["game_state"]
    for relic in game.get("relics", []):
        rid = relic.get("id", relic.get("name", ""))
        relic["name"] = RELIC_ID_TO_BOTTLED_NAME.get(rid, rid)
    for potion in game.get("potions", []):
        pid = potion.get("id", potion.get("name", ""))
        potion["name"] = POTION_ID_TO_BOTTLED_NAME.get(pid, pid)
    return d


def _monsters(bs) -> list[dict[str, Any]]:
    return [{"name": m.name, "hp": m.current_hp, "block": m.block, "gone": bool(m.is_gone)} for m in bs.monsters]


def settle(state: VisibleState, plays: Sequence[Play]) -> SettleResult:
    """按顺序打出 plays，返回结果。只接受战斗中的可见状态。"""
    if state.combat is None:
        return SettleResult(ok=False, reason="当前不在战斗中")

    CardId, RelicId, create_battle_state, deepcopy_state, GameState, MemoryBook = _bottled()

    data = _prepare(state.data)
    hand_raw = data["game_state"]["combat_state"]["hand"]
    bs = create_battle_state(GameState(data, MemoryBook.new_default()))

    known_relics = {r.value for r in RelicId}
    result = SettleResult(
        ok=True,
        monsters_before=_monsters(bs),
        unsupported_cards=[raw["id"] for raw, card in zip(hand_raw, bs.hand) if card.id == CardId.FAKE],
        unrecognized_relics=[
            r["id"] for r in data["game_state"].get("relics", []) if r["name"].lower() not in known_relics
        ],
    )
    hp_before = bs.player.current_hp

    # 手牌的标签：认识的牌用 bottled_ai 的编号，不认识的保留游戏里的内部编号，方便报错
    labels = [_label(raw["id"], raw.get("upgrades", 0)) for raw in hand_raw]

    for step, play in enumerate(plays):
        want = play.card.lower()
        target = -1 if play.target is None else play.target
        idx = next((i for i, lab in enumerate(labels) if lab == want), None)
        if idx is None:
            result.ok, result.failed_step = False, step
            result.reason = f"第 {step + 1} 步：手牌里没有 {play.card}"
            return result
        if bs.hand[idx].id == CardId.FAKE:
            result.ok, result.failed_step = False, step
            result.reason = f"第 {step + 1} 步：{play.card} 无法试算，结算器没有实现这张牌"
            return result
        legal = bs.get_plays()
        if (idx, target) not in legal:
            result.ok, result.failed_step = False, step
            if any(p[0] == idx for p in legal):
                result.reason = f"第 {step + 1} 步：{play.card} 的目标不对"
            else:
                result.reason = f"第 {step + 1} 步：{play.card} 现在打不出，剩余能量 {bs.player.energy}"
            return result

        hand_ids_before = [id(c) for c in bs.hand]
        bs.transform_from_play((idx, target), is_first_play=(step == 0))
        # 出牌后手牌会变（打出的牌离开、抽到的牌用占位牌表示），同步更新标签
        kept = {cid: lab for cid, lab in zip(hand_ids_before, labels)}
        labels = [kept.get(id(c), _label(c.id.value, c.upgrade)) for c in bs.hand]

    result.monsters_after = _monsters(bs)
    result.killed = [
        i
        for i, (before, after) in enumerate(zip(result.monsters_before, result.monsters_after))
        if before["hp"] > 0 >= after["hp"]
    ]
    result.block_after = bs.player.block
    result.energy_left = bs.player.energy
    result.hand_after = labels

    end = deepcopy_state(bs)
    end.end_turn()
    result.hp_lost_after_enemy_turn = hp_before - end.player.current_hp
    return result
