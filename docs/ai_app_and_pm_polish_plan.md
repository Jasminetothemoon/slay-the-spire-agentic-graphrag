# AI 应用开发与 AI 产品经理方向打磨计划

## 目标定位

这个项目不再包装成“游戏 AI”或“普通 GraphRAG Demo”，而是定位为：

> 面向复杂实时决策场景的 Mod-first Multi-Agent Decision Harness，用游戏内 Mod 承载产品体验，用 Agent 工作流、GraphRAG、Decision Skills 和评测 Harness 承载 AI 应用工程能力。

对于 **AI 应用开发**，重点展示工程落地能力：状态接入、低延迟服务、Agent 编排、检索增强、可观测性、评测和回归。

对于 **AI 产品经理**，重点展示产品判断能力：从用户流程痛点出发定义 MVP，用竞品和指标驱动优先级，把主观推荐质量转成可验证的迭代闭环。

## 方向一：AI 应用开发打磨路线

### 简历要讲出的能力

- 能把 LLM/Agent/RAG 从概念落成可用系统，而不是只写 Prompt。
- 能处理真实客户端状态、异常、回放、降级和延迟约束。
- 能设计可扩展 Skill 接口，让不同任务共享 Agent 框架但保留独立策略。
- 能用 Harness 验证效果，说明推荐质量如何被测量、调试和优化。

### 优先级 1：真实 Payload 与评测集扩展

当前已有 JSONL capture/replay 和 54 个固定评测 case。下一步要把评测从“框架可行”推进到“真实可证明”。

要做：

- 用真实游戏运行采集 5 到 10 局 payload，覆盖卡牌奖励、Boss 遗物、商店、战斗、营火。
- 将高价值 payload 转成固定 regression fixtures。
- 人工标注 100 到 200 个关键决策，记录推荐选项、可接受 Top-3、场景理由。
- 在报告中区分“规则命中”“高手策略命中”“可接受但非最优”。

交付物：

- `data/eval_cases/*.json`
- `artifacts/mod_payloads/*.jsonl`
- `reports/decision_harness_report.md`
- README 中的真实 Top-1/Top-3、P95、no recommendation rate。

### 优先级 2：Baseline 与 Ablation 对比

项目最容易被面试官追问的问题是：“GraphRAG 和 Agent 到底带来了什么提升？”

要做：

- 保留当前 deterministic scoring 作为主路径。
- 增加对比模式：
  - Tier baseline：只按卡牌/遗物基础强度排序。
  - Rule baseline：只用规则，不用图谱与流派。
  - GraphRAG + Scoring：当前主方法。
  - GraphRAG + Scoring + Archetype：加入玩家选择的目标流派。
- 输出 ablation 表格，展示 Top-1、Top-3、平均分差、低区分度比例、P95 延迟。

交付物：

- `scripts/decision_harness.py --mode ablation`
- `reports/ablation_report.md`
- 简历量化句：“通过消融实验验证 GraphRAG/流派规则/风险评估对推荐准确率和区分度的贡献”。

### 优先级 3：Agent Trace Audit

Agent 的含金量不应只停留在“用了 LangGraph”。要让每一次推荐都能解释 Agent 如何协作。

要做：

- 为典型场景保存 `agent_trace` 示例。
- 对每个 Agent 记录输入摘要、输出摘要和耗时。
- CriticAgent 把错误分类成：无候选项、场景错配、旧推荐残留、候选项无法匹配、低置信度。
- 在报告中展示一条完整链路：状态解析 -> Skill 路由 -> 图谱检索 -> 风险识别 -> 评分 -> Critic -> UI 输出。

交付物：

- `reports/agent_trace_examples.md`
- Debug 面板显示 trace 摘要。
- 面试讲法：“我没有把多 Agent 做成多个闲聊角色，而是把它们定义为可观测、可回放、可评测的工作流节点。”

### 优先级 4：CI 与本地一键检查

对 AI 应用开发岗位来说，能运行、可维护、可回归很重要。

要做：

- GitHub Actions 跑 Python 单测、数据完整性检查、harness smoke test。
- Windows 本地继续保留 `scripts/dev_check.ps1`。
- 对 Mod 相关构建保留本地脚本，因为依赖用户本机 Slay the Spire、BaseMod、ModTheSpire。

交付物：

- `.github/workflows/ci.yml`
- README CI badge。
- 简历量化句：“建立本地与 CI 双层回归检查，覆盖数据、推荐、replay 和 latency smoke test。”

### 优先级 5：可选异步 LLM 解释

实时推荐不应依赖外部 LLM，这一点是优点。后续可以加一个可选能力：LLM 只负责异步解释增强，不参与核心打分。

要做：

- 推荐接口先返回结构化评分。
- UI 显示即时推荐。
- 后台异步生成更自然的解释，失败时不影响主流程。
- Harness 统计 LLM 成本、延迟和解释可用率。

交付物：

- `explanation_backend=deterministic|llm_async`
- LLM 不可用时自动降级。
- 简历讲法：“核心决策链路不依赖 LLM，LLM 只用于低优先级解释增强，降低实时成本和不确定性。”

## 方向二：AI 产品经理打磨路线

### 简历要讲出的能力

- 能识别用户真实流程痛点，而不是只做技术 Demo。
- 能做竞品分析并转换成产品需求。
- 能定义 MVP、优先级、验收标准和迭代指标。
- 能把主观体验问题转成数据闭环。

### 优先级 1：PRD 与用户旅程

产品经理方向最重要的是说明“为什么做成 Mod，而不是网页”。

要做：

- 写 PRD：目标用户、核心场景、用户痛点、MVP 范围、非目标范围、风险。
- 画用户旅程：启动游戏 -> 进入战斗/奖励/商店 -> 无感看到推荐 -> 展开解释 -> 调整流派 -> 继续游戏。
- 明确核心价值：减少切屏、降低决策负担、帮助学习高手思路、让错误原因可见。

交付物：

- `docs/product_prd.md`
- `docs/user_journey.md`
- README 增加 Product Positioning 链接。

当前状态：

- 已补齐 PRD 与用户旅程文档，可直接作为 AI 产品经理方向材料。

### 优先级 2：竞品分析与差异化

要把 STS Checker Run Companion、StsCompanion、Knowledge Demon、STS2.GG 等竞品转成需求来源。

要做：

- 对比竞品能力：游戏内 overlay、奖励评分、商店建议、路线建议、run history、社区数据、个性化模型。
- 标出本项目当前已有、缺失、计划中功能。
- 给每个缺失能力打价值分、实现成本、风险。

交付物：

- `docs/competitor_analysis.md`
- `docs/feature_priority_matrix.md`
- 面试讲法：“我不是为了炫技堆 Agent，而是基于竞品和用户流程重新定义产品形态，把网页降级为调试台，把 Mod 变成核心入口。”

当前状态：

- 已补齐竞品分析与功能优先级矩阵，后续可随着新竞品或真实用户反馈迭代。

### 优先级 3：产品指标体系

AI 产品经理方向要避免只说“推荐更好”。必须说明怎么衡量。

指标建议：

- 激活指标：Mod 是否连接成功、API 首次响应成功率。
- 使用指标：每局触发推荐次数、F8/F9/F10/F11 使用次数、hover 详情查看率。
- 质量指标：Top-1/Top-3 命中率、低区分度比例、跳过卡牌排序、错误推荐率。
- 体验指标：P95 延迟、无推荐率、用户可见失败原因覆盖率。
- 学习指标：用户是否修改流派、是否查看 why_not、是否接受非默认推荐。

交付物：

- `docs/product_metrics.md`
- Harness 报告映射产品指标。
- 简历讲法：“定义推荐质量、实时性和可观测性指标，将主观策略体验转化为可持续迭代的数据闭环。”

当前状态：

- 已补齐指标体系文档，下一步需要把用户行为事件接入 Mod 和 harness。

### 优先级 4：产品 Roadmap

推荐路线：

1. 当前版本：游戏内推荐可见、双语、流派选择、Debug、harness。
2. 下一版：真实 payload 扩展、Boss 遗物/商店/营火强化、候选项 badge 完整覆盖。
3. 强化版：事件助手、地图 3-5 层 lookahead、个人 run history。
4. 产品化版：配置页、用户反馈按钮、推荐接受/忽略统计、社区规则导入。
5. 展示版：报告页、案例库、面试演示脚本。

### 优先级 5：用户反馈闭环

后续要让用户能直接在游戏内反馈推荐质量。

要做：

- F9 Debug 或快捷键记录“推荐有用/无用”。
- 保存用户选择和系统推荐的差异。
- 将失败案例进入 replay harness。
- 对低分差、低置信度、用户反复忽略的推荐做标记。

交付物：

- `artifacts/user_feedback/*.jsonl`
- `reports/feedback_analysis.md`

## 综合实施顺序

| 顺序 | 任务 | 偏向 | 价值 | 成本 |
| ---: | --- | --- | --- | --- |
| 1 | 写 PRD、用户旅程、产品指标 | AI PM | 高 | 低 |
| 2 | 扩展真实 payload 与 replay fixtures | AI 应用开发 | 最高 | 中 |
| 3 | Baseline/Ablation 报告完善 | AI 应用开发 | 最高 | 中 |
| 4 | 竞品分析与优先级矩阵 | AI PM | 高 | 低 |
| 5 | Agent Trace Audit 报告 | 双方向 | 高 | 中 |
| 6 | GitHub Actions CI | AI 应用开发 | 中高 | 中 |
| 7 | 用户反馈闭环 | 双方向 | 高 | 中高 |
| 8 | 可选异步 LLM 解释 | AI 应用开发 | 中 | 中 |

## 最适合写进简历的最终形态

### AI 应用开发版本

> 构建《杀戮尖塔》实时游戏内 AI 决策助手，基于 Java Mod + FastAPI 接入真实游戏状态，通过 LangGraph 编排 State/Router/Retrieval/Risk/Scoring/Critic/Explainer 多 Agent 工作流，结合 Neo4j GraphRAG、本地降级缓存与可插拔 Decision Skills 输出低延迟结构化推荐，并使用 replay/eval/ablation/latency harness 量化推荐质量与系统稳定性。

### AI 产品经理版本

> 主导设计一款面向复杂策略游戏的 AI 决策辅助产品，基于用户切屏成本高、推荐不可解释、策略学习门槛高等痛点，将方案从网页 Demo 重构为游戏内 Mod-first 体验；完成竞品拆解、MVP 范围定义、双语交互、流派选择、失败可见性、推荐质量指标和 replay 评测闭环设计。

## 结论

这个项目对于 AI 应用开发方向已经具备比较强的简历价值，因为它覆盖了 Agent、RAG、工程服务、实时状态接入、评测和产品 UI。对于 AI 产品经理方向，PRD、竞品分析、用户旅程和指标体系的基础材料已经补齐，下一步要把用户反馈闭环接入真实 Mod 使用数据。现在它不是“小儿科项目”，而是一个能同时体现技术理解和产品判断的 AI 应用作品。
