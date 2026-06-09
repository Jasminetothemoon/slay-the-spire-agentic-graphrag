# 竞品分析：游戏内 AI/数据辅助工具

## 资料范围

本分析基于 2026-06-09 可访问的公开页面和项目资料。由于部分工具仍在快速迭代，本文只把公开可见能力作为产品启发，不把它们视为完全验证过的内部实现。

参考来源：

- [StsCompanion / Card Rewards Helper](https://www.nexusmods.com/slaythespire2/mods/340)
- [Knowledge Demon Data Overlay](https://sts2.gg/mods/mod-110)
- [STS2.GG Tools](https://sts2.gg/tools)
- [STS2.GG Reward Helper](https://sts2.gg/tools/reward-helper)
- [STS2.GG Boss Relic Picker](https://sts2.gg/tools/boss-relic-picker)
- [STS2.GG Rest Site Optimizer](https://sts2.gg/tools/rest-site-optimizer)
- [Spire Codex Overlay discussion](https://www.reddit.com/r/slaythespire/comments/1thbrjw/spire_codex_now_has_a_free_ingame_overlay_for/)
- [SpireSense](https://www.spiresense.app/)

## 竞品拆解

### 1. StsCompanion / Card Rewards Helper

公开页面显示它的核心卖点是卡牌奖励辅助、游戏内 Mod 形式、不同数据模式和社区数据支持。

值得学习：

- 游戏内直接显示推荐，不要求用户切网页。
- 把卡牌奖励作为最高频场景优先做深。
- 用社区数据或统计数据增强推荐可信度。
- 产品入口轻量，用户理解成本低。

本项目对应策略：

- 已实现游戏内推荐面板和候选项 Badge。
- 已支持目标流派选择。
- 后续应增强真实玩家数据或社区规则的来源追踪。

### 2. Knowledge Demon Data Overlay

公开说明强调 Data Overlay、卡牌奖励、商店、休息点、升级、遗物选择、数据来源切换等能力。

值得学习：

- 覆盖多个高频决策点，而不是只做卡牌。
- Overlay 融入游戏流程。
- 允许用户在不同数据视角之间切换，例如个人数据或顶级玩家数据。
- 强调“数据辅助”，降低用户对 AI 黑箱的抵触。

本项目对应策略：

- 当前已覆盖卡牌、遗物、Boss 遗物、商店、战斗、营火 skill。
- 需要进一步强化商店、营火和 Boss 遗物质量。
- 后续可以加入“个人选择历史”和“社区策略规则”两种视角。

### 3. STS2.GG 工具体系

STS2.GG 提供 reward helper、boss relic picker、rest site optimizer 等工具，说明市场上高价值决策被拆成了多个专门工具。

值得学习：

- 选牌推荐需要考虑 deck needs、curve、archetype fit。
- Boss 遗物推荐需要考虑能量需求、卡组稳定性和副作用。
- 营火决策需要结合血量、升级价值和下一场风险。
- 单点工具可以很强，但用户仍然要离开游戏或手动输入。

本项目对应策略：

- 用 Decision Skills 吸收这种“每类决策单独建模”的思想。
- 用 Mod 自动读取状态，减少手动输入。
- 用 unified harness 比较不同技能质量。

### 4. Spire Codex Overlay

公开讨论强调游戏内 overlay、run tracker 和资料查询，核心启发是让知识库能力从网页进入游戏内。

值得学习：

- Overlay 是策略游戏辅助工具的关键入口。
- 查资料、看记录、看推荐可以放在同一个伴随式体验里。
- 无需 alt-tab 是明确卖点。

本项目对应策略：

- 当前网页端定位为调试台，而不是主产品。
- 后续可把百科/规则证据做成 hover 或 debug drill-down，而不是独立百科站。

### 5. SpireSense

公开页面强调 overlay、run history、个性化和 AI coach 等方向。

值得学习：

- 个性化是下一阶段竞争点。
- Run history 能把单局推荐升级为长期成长工具。
- AI coach 的价值不只是告诉用户选什么，还要帮助用户理解为什么。

本项目对应策略：

- 当前已有解释、why_not 和目标流派。
- 后续可加入用户反馈、实际选择记录和 run history。
- LLM 更适合做异步 coach 总结，而不是实时打分。

## 横向能力对比

| 能力 | 竞品趋势 | 本项目当前状态 | 缺口 |
| --- | --- | --- | --- |
| 游戏内 Overlay | 头部工具都强调无切屏 | 已有推荐面板、Badge、F8/F9/F10/F11 | UI polish 和稳定性仍需打磨 |
| 卡牌奖励 | 高频核心场景 | 已支持 CardPickSkill、Skip、流派 | 需要更多真实标注和社区策略 |
| 遗物/Boss 遗物 | 高价值场景 | 已支持 RelicPickSkill | 副作用建模还可增强 |
| 商店 | 高价值且复杂 | 已支持 ShopSkill | 需要更细价格/删牌/药水机会成本 |
| 营火/升级 | 竞品有专门工具 | 已支持 RestSiteSkill | 需要更高质量升级目标 |
| 地图路线 | 高端玩家重视 | 后端有 PathingSkill，Mod live 暂保守关闭 | 需要稳定采集和 3-5 层 lookahead |
| 事件助手 | 决策频繁 | 未完成 | 后续 P2 |
| Run history | 个性化基础 | 未完成 | 后续 P2/P3 |
| 社区数据 | 竞品重要卖点 | 有社区规则和 provenance | 缺真实统计接入 |
| AI Coach | 新兴卖点 | 暂无 LLM 实时链路 | 可做异步总结 |
| 评测 Harness | 公开工具较少强调 | 已有 replay/eval/ablation/latency | 这是本项目差异化亮点 |
| 多 Agent/Skill | 竞品不一定强调 | 已有 LangGraph + Skill System | 需要 trace case study 展示 |

## 本项目差异化

### 差异化 1：Mod-first + Harness

竞品多强调游戏内体验和数据推荐。本项目额外强调工程可验证性：

- 每个实机 payload 可保存。
- 每个问题可 replay。
- 每个模块可 ablation。
- 每个推荐有 agent_trace 和 critic_warnings。

这对 AI 应用开发求职很有价值。

### 差异化 2：Agent 不是聊天，而是决策工作流

本项目的 Agent 不是“多个 LLM 角色讨论”，而是：

- StateAgent 处理状态。
- RouterAgent 选 Skill。
- RetrievalAgent 找证据。
- RiskAgent 找风险。
- SkillScoringAgent 打分。
- CriticAgent 防止错误输出。
- ExplainerAgent 生成 UI 文案。

这更贴近生产系统中的 workflow orchestration。

### 差异化 3：产品入口明确

本项目明确放弃“网页是主产品”，而是：

- 游戏内 Mod 做主入口。
- 网页做调试、评测、报告展示。
- 长期再考虑知识浏览器。

这个取舍体现 AI 产品经理视角。

## 从竞品提炼出的功能机会

| 优先级 | 功能机会 | 来源启发 | 用户价值 | 实现成本 |
| ---: | --- | --- | --- | --- |
| 1 | 更强卡牌奖励质量 | StsCompanion / STS2.GG | 最高频 | 中 |
| 2 | 商店结构化建议 | Knowledge Demon / STS2.GG | 决策复杂 | 中 |
| 3 | Boss 遗物副作用解释 | STS2.GG Boss Relic Picker | 高影响 | 中 |
| 4 | 营火 Rest/Smith/Upgrade | Rest Site Optimizer | 高频 | 中 |
| 5 | 真实 run history | SpireSense / Overlay 工具 | 个性化 | 高 |
| 6 | 用户反馈按钮 | AI 产品闭环 | 质量迭代 | 中 |
| 7 | 地图路线 lookahead | 高端玩家需求 | 高 | 高 |
| 8 | 事件助手 | 游戏完整性 | 中 | 中 |
| 9 | 异步 AI Coach | SpireSense 类方向 | 学习价值 | 中高 |
| 10 | 百科/知识浏览器 | Spire Codex | 辅助价值 | 低到中 |

## 产品结论

如果目标是 AI 应用开发实习，本项目下一步应该优先补：

1. 真实 payload。
2. Baseline/ablation 报告。
3. Agent trace audit。
4. CI 和 regression。

如果目标是 AI 产品经理实习，本项目下一步应该优先补：

1. PRD。
2. 竞品分析。
3. 用户旅程。
4. 产品指标。
5. 功能优先级矩阵。

当前最好的策略是双轨：继续强化 AI 应用开发主线，同时用产品文档把“为什么这样做”讲清楚。
