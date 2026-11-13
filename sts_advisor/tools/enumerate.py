"""计算工具：单回合枚举。

只看本回合时，程序能算出的最优出牌。它不知道之后几回合会怎样，也不模拟抽到什么牌。
两个用途（见 docs/v2_design.md 改动点 7、11）：
- 战斗顾问的计划没通过核对时，用它的结果顶上；
- 评测里的基线：LLM 的规划比传统程序多带来什么。

实现方式：直接用 bottled_ai 自带的枚举和打分规则。
"""
from __future__ import annotations

from sts_advisor.ingest.visible_state import VisibleState
from sts_advisor.tools.settle import Play, _advance, _bottled, _hand_labels, _prepare

# 手牌多、敌人多时枚举会超过一秒，所以默认设一个上限。上限内没枚举完时，结果可能不是最优。
DEFAULT_MAX_PATHS = 3000


def best_single_turn(state: VisibleState, max_paths: int = DEFAULT_MAX_PATHS) -> list[Play]:
    """返回只看本回合时的最优出牌顺序。空列表表示直接结束回合。"""
    if state.combat is None:
        return []
    _, _, create_battle_state, _, GameState, MemoryBook = _bottled()
    from rs.calculator.executor import get_best_battle_path
    from rs.common.comparators.common_general_comparator import CommonGeneralComparator

    data = _prepare(state.data)
    path = get_best_battle_path(GameState(data, MemoryBook.new_default()), CommonGeneralComparator(), max_paths)
    if path is None:
        return []

    # 把「手牌下标」翻译回牌名：一边重放一边记手牌的变化
    bs = create_battle_state(GameState(data, MemoryBook.new_default()))
    labels = _hand_labels(data["game_state"]["combat_state"]["hand"])
    plays: list[Play] = []
    for step, (idx, target) in enumerate(path.plays):
        if target < -1 or idx >= len(labels):
            # 弃牌、消耗这类需要玩家选牌的后续动作，这里不展开
            break
        plays.append(Play(labels[idx], None if target == -1 else target))
        labels = _advance(bs, labels, idx, target, first=(step == 0))
    return plays
