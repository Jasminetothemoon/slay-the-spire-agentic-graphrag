"""计算工具：一回合的「形状」——每回合有几点能量、抽几张牌。

战斗中这些直接看得到（当前的手牌和能量就在状态里）。
战斗外做牌组体检时看不到，要从遗物推出来：默认每回合 3 点能量、抽 5 张，遗物会改变它。

这里只收录确定会改变每回合能量或抽牌数的遗物。按条件触发的没有计入，
其中对结果影响大的会写进 notes，提醒读结果的人。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

BASE_ENERGY = 3
BASE_HAND = 5
MAX_HAND = 10  # 手牌上限

# 键都是游戏内部的遗物编号
ENERGY_EVERY_TURN = frozenset(
    {
        "Busted Crown",
        "Coffee Dripper",
        "Cursed Key",
        "Ectoplasm",
        "Fusion Hammer",
        "Mark of Pain",
        "Philosopher's Stone",
        "Runic Dome",
        "Sozu",
        "Velvet Choker",
    }
)
ENERGY_FIRST_TURN = {"Lantern": 1}
DRAW_EVERY_TURN = {"Snecko Eye": 2, "Ring of the Serpent": 1}
DRAW_FIRST_TURN = {"Ring of the Snake": 2, "Bag of Preparation": 2}

NOTES = {
    "Snecko Eye": "带着异蛇之眼：抽到的牌费用会随机变成 0 到 3，这里仍按原费用计算，结果只能当参考",
    "SlaversCollar": "带着奴隶贩子颈环：精英和 Boss 战多 1 点能量，这里没有计入",
    "Happy Flower": "带着开心小花：每三回合多 1 点能量，这里没有计入",
    "Ice Cream": "带着冰淇淋：没用完的能量会留到下回合，这里没有计入",
    "Runic Pyramid": "带着符文金字塔：回合结束不弃牌，实际手牌会比这里算的多",
}


@dataclass(frozen=True)
class TurnShape:
    energy: int = BASE_ENERGY
    hand_size: int = BASE_HAND
    first_turn_energy: int = BASE_ENERGY
    first_turn_hand_size: int = BASE_HAND
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def first_turn_differs(self) -> bool:
        return (self.first_turn_energy, self.first_turn_hand_size) != (self.energy, self.hand_size)


def turn_shape(relics: list[dict[str, Any]] | None) -> TurnShape:
    """从持有的遗物推出每回合的能量和抽牌数。"""
    ids = [r.get("id", "") for r in relics or []]
    energy = BASE_ENERGY + sum(1 for i in ids if i in ENERGY_EVERY_TURN)
    hand = BASE_HAND + sum(DRAW_EVERY_TURN.get(i, 0) for i in ids)
    return TurnShape(
        energy=energy,
        hand_size=min(hand, MAX_HAND),
        first_turn_energy=energy + sum(ENERGY_FIRST_TURN.get(i, 0) for i in ids),
        first_turn_hand_size=min(hand + sum(DRAW_FIRST_TURN.get(i, 0) for i in ids), MAX_HAND),
        notes=tuple(NOTES[i] for i in ids if i in NOTES),
    )
