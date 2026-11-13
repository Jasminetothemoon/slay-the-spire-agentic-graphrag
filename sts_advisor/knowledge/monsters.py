"""知识层：怪物招式表。

每个敌人有哪些招式、按什么规则选招、有什么要注意的机制。
数据在同目录的 monsters.json，来源和核对情况写在它的 _about 里。
目前只有第一幕的精英和 Boss、进阶 0 的数值。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).with_name("monsters.json")


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def about() -> dict[str, Any]:
    """数据的范围、来源和核对情况。"""
    return dict(_load()["_about"])


def known_ids() -> list[str]:
    return sorted(k for k in _load() if not k.startswith("_"))


def lookup_by_name(name_en: str) -> dict[str, Any] | None:
    """按英文名查。游戏状态里的 act_boss 给的是英文名而不是内部编号。"""
    for monster_id in known_ids():
        if _load()[monster_id].get("name_en", "").lower() == name_en.strip().lower():
            return lookup(monster_id)
    return None


def lookup(monster_id: str) -> dict[str, Any] | None:
    """按游戏内部编号查一个敌人。没有收录时返回 None。"""
    if monster_id.startswith("_"):
        return None
    entry = _load().get(monster_id)
    return dict(entry, id=monster_id) if entry else None
