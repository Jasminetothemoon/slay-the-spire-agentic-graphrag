"""计算工具：抽牌概率。

抽牌堆里有哪些牌是已知的，顺序未知，所以抽到某张牌的可能性是一个组合计算。
抽牌堆抽空后，弃牌堆会洗进来接着抽，这里一并处理。
"""
from __future__ import annotations

from math import comb
from typing import Callable, Iterable, Sequence

Card = str
Wanted = Callable[[Card], bool]


def _as_predicate(wanted: Wanted | Iterable[Card] | Card) -> Wanted:
    if callable(wanted):
        return wanted
    if isinstance(wanted, str):
        return lambda c: c == wanted
    targets = set(wanted)
    return lambda c: c in targets


def _hypergeom_at_least(population: int, hits: int, draws: int, at_least: int) -> float:
    """从 population 张里不放回抽 draws 张，其中 hits 张是想要的，至少抽到 at_least 张的概率。"""
    if at_least <= 0:
        return 1.0
    draws = min(draws, population)
    if draws <= 0 or hits < at_least:
        return 0.0
    total = comb(population, draws)
    ways = sum(
        comb(hits, k) * comb(population - hits, draws - k)
        for k in range(at_least, min(hits, draws) + 1)
        if draws - k <= population - hits
    )
    return ways / total


def draw_probability(
    draw_pile: Sequence[Card],
    wanted: Wanted | Iterable[Card] | Card,
    draws: int,
    at_least: int = 1,
    discard_pile: Sequence[Card] = (),
) -> float:
    """接下来抽 draws 张牌，至少抽到 at_least 张想要的牌的概率。

    draw_pile、discard_pile 是牌名列表，顺序无关。
    wanted 可以是一个牌名、一组牌名，或一个判断函数。
    """
    if draws < 0 or at_least < 0:
        raise ValueError("draws 和 at_least 不能为负")
    is_wanted = _as_predicate(wanted)

    n_draw = len(draw_pile)
    k_draw = sum(1 for c in draw_pile if is_wanted(c))

    # 抽牌堆够抽：只看抽牌堆
    if draws <= n_draw:
        return _hypergeom_at_least(n_draw, k_draw, draws, at_least)

    # 抽牌堆不够：抽牌堆整个抽完，剩下的从洗回来的弃牌堆里抽
    remaining_draws = draws - n_draw
    still_needed = at_least - k_draw
    n_disc = len(discard_pile)
    k_disc = sum(1 for c in discard_pile if is_wanted(c))
    return _hypergeom_at_least(n_disc, k_disc, remaining_draws, still_needed)
