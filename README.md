# 杀戮尖塔局内助手

《杀戮尖塔》一代的局内助手：玩家打游戏时，在抓牌、篝火、战斗出牌等决策点给建议，并用新手听得懂的话解释为什么。判断、规划和讲解交给 LLM；算术由程序做成工具供 LLM 调用；LLM 说的每句话由程序核对。

完整设计和第一版的复盘见 [docs/v2_design.md](docs/v2_design.md)。

## 当前状态

v2 正在重建，下表是每一层的实际进度。没有列为「已实现」的都还没有代码。

| 层 | 模块 | 状态 |
| --- | --- | --- |
| 接入层 | 可见状态过滤、决策类型识别（`sts_advisor/ingest`） | 已实现，有测试。还没有接真实游戏 |
| 计算工具 | 抽牌概率（`sts_advisor/tools/draw_odds.py`） | 已实现，有测试 |
| 计算工具 | 结算器（`sts_advisor/tools/settle.py`） | 已实现，有测试。跨调用的计数还没接，见文件开头的说明 |
| 计算工具 | 单回合枚举（`sts_advisor/tools/enumerate.py`） | 已实现，有测试 |
| 计算工具 | 牌组体检（`sts_advisor/tools/deck_checkup.py`） | 已实现，有测试。算的有伤害、群伤、格挡、过牌、费用；成长和回复只列出候选牌。每回合抽几张、几点能量按遗物推算。考验表只有第一幕，且没有校准过 |
| 知识层 | 怪物招式表（`sts_advisor/knowledge/monsters.json`） | 只有第一幕的 3 个精英和 3 个 Boss，进阶 0 的数值。对着开源引擎的源码核对过，没有对照真实游戏验证 |
| 知识层 | 规则库、图谱、统计信号 | 未实现 |
| 判断层 | 战斗顾问（`sts_advisor/agents/combat.py`） | 已实现，默认用 DeepSeek。测试用的是按脚本回答的假模型，还没有用真实模型跑过，没有任何效果数字 |
| 判断层 | 构筑顾问（`sts_advisor/agents/deckbuilding.py`） | 抓牌已实现，篝火、商店、Boss 遗物没有。和战斗顾问一样，还没有用真实模型跑过 |
| 判断层 | 本局计划 | 未实现 |
| 校验与呈现 | 核对（在两个顾问里） | 战斗：出牌是否合法、有没有漏掉斩杀。抓牌：选项是否存在、理由引用的体检指标方向对不对。理由文字里的数字还不核对 |
| 校验与呈现 | 其余校验、讲解教练、悬浮窗 | 未实现 |
| 评测 | 指标与基线 | 未实现 |

## 目录

```
sts_advisor/     v2 代码，按设计文档的五层分包
tests/           v2 的测试
docs/            v2 设计文档
third_party/     bottled_ai 子模块，结算器包装它的单回合计算模块
```

## 运行测试

需要 Python 3.11 或更高版本。测试不联网、不调用模型。

```bash
git submodule update --init third_party/bottled_ai
pip install -e .
python -m unittest discover -s tests -t .
```

## 试一次战斗建议

会真实调用模型，产生费用。默认用 DeepSeek，需要先设置环境变量 `DEEPSEEK_API_KEY`。想换成 Claude，先 `pip install -e ".[claude]"`，再设置 `STS_ADVISOR_PROVIDER=claude` 和 `ANTHROPIC_API_KEY`。

```bash
# 战斗中的一回合
python -m sts_advisor.cli third_party/bottled_ai/tests/res/battles/general/battle_simple_state.json
# 战斗后的抓牌
python -m sts_advisor.cli third_party/bottled_ai/tests/res/card_reward/card_reward_skip.json
```

## 第一版

第一版是一个规则打分器，带 FastAPI 桥接和网页悬浮窗。它的代码已从主分支删除，完整保留在标签 `v1`（提交 `11c5c69`）里，用 `git checkout v1` 可以查看。它和当时的设计文档不一致的地方，以及为什么重建，写在设计文档的「v1 复盘」一节。

## 出处

- 结算器包装了 [bottled_ai](https://github.com/xaved88/bottled_ai) 的单回合计算模块（MIT 许可，Logan Bentley 与 Robert Aiking）。
- 游戏状态来自 [CommunicationMod](https://github.com/ForgottenArbiter/CommunicationMod)。
