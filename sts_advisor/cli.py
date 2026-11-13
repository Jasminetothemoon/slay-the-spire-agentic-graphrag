"""命令行入口：对一个录下来的游戏状态给出建议。会真实调用模型，产生费用。

用法：python -m sts_advisor.cli <CommunicationMod 状态的 JSON 文件>

按状态所在的界面自动选顾问：战斗中的出牌回合交给战斗顾问，战斗后的抓牌交给构筑顾问。
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict

from sts_advisor.agents.combat import CombatAdvisor
from sts_advisor.agents.deckbuilding import DeckAdvisor
from sts_advisor.agents.llm import default_model
from sts_advisor.ingest.visible_state import Decision, to_visible


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    with open(args[0], encoding="utf-8") as f:
        state = to_visible(json.load(f))

    if state.decision == Decision.COMBAT_TURN:
        advice = CombatAdvisor(default_model()).advise(state)
    elif state.decision == Decision.CARD_REWARD:
        advice = DeckAdvisor(default_model()).advise(state)
    else:
        print(f"这个界面还没有对应的顾问（识别为 {state.decision.value}）", file=sys.stderr)
        return 1
    print(json.dumps(asdict(advice), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
