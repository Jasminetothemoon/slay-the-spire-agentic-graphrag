"""接入层：把 CommunicationMod 推送的完整状态变成「可见状态」。

边界规则（见 docs/v2_design.md 改动点 1）：
玩家凭屏幕上的信息加公开规则能推出来的，可以用；
需要种子或内存里的隐藏顺序才能知道的，不向下传。

本模块是唯一接触原始状态的地方。其他层只拿 VisibleState。
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from enum import Enum
from typing import Any

FROZEN_EYE = "Frozen Eye"
RUNIC_DOME = "Runic Dome"

# 怪物身上透露「这回合要做什么」的字段。持有符文圆顶时游戏不显示意图，这些要去掉。
# last_move_id 等是已经发生过的招式，玩家看得到，保留。
INTENT_KEYS = ("move_id", "move_base_damage", "move_adjusted_damage", "move_hits")


class Decision(str, Enum):
    """当前屏幕对应哪种决策。第一期只处理前三种。"""

    COMBAT_TURN = "combat_turn"
    CARD_REWARD = "card_reward"
    CAMPFIRE = "campfire"
    OTHER = "other"


@dataclass(frozen=True)
class VisibleState:
    """过滤后的状态。data 的结构与 CommunicationMod 的消息相同，只是去掉了隐藏信息。"""

    decision: Decision
    data: dict[str, Any]
    filtered: tuple[str, ...]  # 这次过滤掉了什么，给日志和测试用

    @property
    def game(self) -> dict[str, Any]:
        return self.data.get("game_state", {})

    @property
    def combat(self) -> dict[str, Any] | None:
        return self.game.get("combat_state")


def _relic_ids(game: dict[str, Any]) -> set[str]:
    return {r.get("id", "") for r in game.get("relics", [])}


def _card_sort_key(card: dict[str, Any]) -> tuple:
    return (card.get("id", ""), card.get("upgrades", 0), card.get("cost", 0), card.get("uuid", ""))


def _detect_decision(game: dict[str, Any]) -> Decision:
    screen = game.get("screen_type")
    if game.get("room_phase") == "COMBAT" and "combat_state" in game:
        # 战斗中弹出的选牌界面（弃牌、发现等）暂不处理
        return Decision.COMBAT_TURN if screen == "NONE" else Decision.OTHER
    if screen == "CARD_REWARD":
        return Decision.CARD_REWARD
    if screen == "REST":
        return Decision.CAMPFIRE
    return Decision.OTHER


def to_visible(raw: dict[str, Any]) -> VisibleState:
    """过滤原始状态。不修改传入的对象。"""
    data = copy.deepcopy(raw)
    game = data.get("game_state")
    if not data.get("in_game") or not isinstance(game, dict):
        return VisibleState(Decision.OTHER, data, ())

    filtered: list[str] = []

    # 1. 种子：只能用来推算随机结果，丢掉
    for key in [k for k in game if "seed" in k.lower()]:
        del game[key]
        filtered.append(key)

    relics = _relic_ids(game)
    combat = game.get("combat_state")
    if isinstance(combat, dict):
        # 2. 抽牌堆顺序：玩家看得到有哪些牌，看不到顺序。
        #    按固定规则排序，等于丢掉顺序信息，同时让相同的牌堆得到相同的表示。
        #    持有冰冻之眼时游戏本身显示顺序，保留。
        if FROZEN_EYE not in relics and "draw_pile" in combat:
            combat["draw_pile"] = sorted(combat["draw_pile"], key=_card_sort_key)
            filtered.append("draw_pile_order")

        # 3. 敌人意图：持有符文圆顶时游戏不显示
        if RUNIC_DOME in relics:
            for monster in combat.get("monsters", []):
                for key in INTENT_KEYS:
                    monster.pop(key, None)
                monster["intent"] = "UNKNOWN"
            filtered.append("monster_intent")

    return VisibleState(_detect_decision(game), data, tuple(filtered))
