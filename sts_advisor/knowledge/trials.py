"""知识层：考验表。每一幕里最考验牌组的敌人，以及考验的是哪项能力。

数据在同目录的 trials.json，目前只有第一幕，是没有校准过的初始设定。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).with_name("trials.json")


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def about() -> dict[str, Any]:
    return dict(_load()["_about"])


def for_act(act: int) -> list[dict[str, Any]]:
    """某一幕的考验。没有收录的幕返回空列表。"""
    return [dict(e) for e in _load().get(str(act), [])]
