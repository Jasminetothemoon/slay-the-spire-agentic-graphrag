# Resume Project Summary

## Project Title

Mod-first Multi-Agent Decision Harness for Slay the Spire

## One-Line Pitch

Built a real-time in-game AI decision assistant that combines a Java Mod bridge, LangGraph multi-agent workflow, pluggable Decision Skills, GraphRAG retrieval, deterministic scoring, and replay/evaluation harnesses for complex strategy-game decisions.

## Resume Bullets

- Built a ModTheSpire/BaseMod in-game assistant that reads live Slay the Spire run state, calls a local FastAPI recommendation service, and renders candidate score badges, hover explanations, target archetype controls, and Chinese/English UI directly inside the game.
- Designed a LangGraph workflow with State, Scene Router, Retrieval, Risk, Skill Scoring, Critic, and Explainer agents; exposed structured `agent_trace`, `selected_skill`, critic warnings, and decision validity for debugging and replay.
- Implemented a pluggable Decision Skill system covering card picks, relic picks, shops, pathing, combat turns, and rest-site decisions, with deterministic scoring instead of external LLM calls in the real-time path.
- Built a provenance-tracked knowledge graph from public game data with 666 entities and 1442 relationships; supported Neo4j GraphRAG retrieval with local JSON fallback for reliable offline demos.
- Added replay/eval/ablation/latency harnesses over 54 fixed scenarios and real Mod JSONL payloads; compared the full system against input-order and base-value baselines, reported Top-1/Top-3, P95 latency, no-recommendation rate, critic warnings, and tuning flags such as low score separation.

## AI 应用开发方向简历版本

### 项目名称

《杀戮尖塔》实时游戏内 Multi-Agent 决策助手

### 一句话版本

构建一个 Mod-first AI 决策系统，通过 Java Mod 接入真实游戏状态，使用 FastAPI、LangGraph 多 Agent、Neo4j GraphRAG、本地降级缓存和可插拔 Decision Skills 输出低延迟结构化推荐，并用 replay/eval/ablation/latency harness 量化推荐质量。

### 简历 Bullet

- 基于 ModTheSpire/BaseMod + FastAPI 构建实时游戏内 AI 推荐助手，自动读取卡组、遗物、商店、奖励、战斗等状态，并在游戏内渲染候选项评分、hover 解释、Debug 面板、中英文切换和目标流派控制。
- 设计 LangGraph 多 Agent 工作流，将推荐链路拆分为 State、Scene Router、Retrieval、Risk、Skill Scoring、Critic、Explainer 节点，输出 `agent_trace`、`selected_skill`、critic warnings 和结构化解释，提升可观测性与可调试性。
- 实现可插拔 Decision Skill 系统，覆盖选牌、遗物、商店、路线、战斗和营火决策；实时链路使用 deterministic scoring，不依赖外部 LLM，保证低延迟、低成本和可回归。
- 构建包含 666 个实体、1442 条关系的来源可追踪知识图谱，支持 Neo4j GraphRAG 检索与本地 JSON fallback，内部使用稳定英文 id，展示层支持中文/英文名称。
- 搭建 replay/eval/ablation/latency harness，支持真实 Mod JSONL payload 回放、固定局面 Top-1/Top-3 评测、朴素基线对比、模块消融和 P95 延迟统计；当前 curated eval 中完整系统 Top-1/Top-3 为 1.0/1.0，base-value 基线为 0.593/0.759，关闭 strategy 后 Top-1 降至 0.87。

### 面试主线

重点讲“真实 AI 应用落地”：

- 为什么实时链路不调用 LLM：延迟、成本、稳定性和可回归。
- 为什么需要 Agent：每个 Agent 负责一个可观测的工程环节，不是多个聊天机器人。
- 为什么需要 Harness：把实机错误、推荐不准和 UI 状态错配转成可复现测试。
- 为什么 Neo4j 而不是 NetworkX：持久化、多跳查询、Cypher、证据链和未来扩展。

## AI 产品经理方向简历版本

### 项目名称

复杂策略游戏 AI 决策助手产品设计与落地

### 一句话版本

围绕玩家切屏成本高、策略学习门槛高、推荐不可解释等痛点，将最初网页 Demo 重构为游戏内 Mod-first AI 助手，设计 MVP、双语交互、目标流派选择、失败可见性、推荐质量指标和 replay 评测闭环。

### 简历 Bullet

- 基于真实游戏流程痛点重定义产品形态，将网页助手降级为调试台，把游戏内 Mod 作为核心入口，实现玩家无需切屏即可查看推荐、理由、风险和候选项分数。
- 拆解 STS Companion、Run Companion、Knowledge Demon、STS2.GG 等同类产品能力，沉淀游戏内 overlay、奖励评分、商店建议、流派适配、Debug 可见性和评测闭环等需求优先级。
- 设计 MVP 与阶段路线：先保证卡牌/遗物/商店推荐可见和可解释，再扩展真实 payload、Boss 遗物、营火、路线、事件、用户反馈和个性化统计。
- 定义 AI 推荐产品指标体系，包括 Top-1/Top-3 命中率、P95 延迟、无推荐率、错误原因可见率、低区分度比例、skip rank、用户查看解释和切换流派行为。
- 推动推荐体验从“自然语言建议”升级为“结构化评分 + why_not + 风险提示 + 可回放失败 case”，让主观策略质量进入可度量、可复盘、可迭代的产品闭环。

### 面试主线

重点讲“AI 产品判断”：

- 用户为什么不用网页：游戏内场景下切屏会打断体验。
- 为什么先做 Mod 而不是百科：百科不是高频痛点，实时决策才是核心价值。
- 为什么保留 Debug 面板：AI 产品失败不可避免，关键是让失败原因对用户和开发者可见。
- 为什么做流派选择：同一个选项在不同目标下价值不同，用户意图必须进入推荐链路。
- 如何衡量推荐质量：用评测集、replay、消融和用户反馈替代主观感受。

### 产品材料入口

- PRD：`docs/product_prd.md`
- 用户旅程：`docs/user_journey.md`
- 竞品分析：`docs/competitor_analysis.md`
- 功能优先级：`docs/feature_priority_matrix.md`
- 指标体系：`docs/product_metrics.md`

## 项目实施精华

## Interview Talking Points

### Why This Is More Than a Game Bot

The project is framed as a complex decision-support system under real-time constraints. Slay the Spire provides rich state, partial future risk, archetype-dependent choices, and high variance, which makes it a useful proxy for AI application problems such as retrieval, workflow orchestration, evaluation, and explainable recommendations.

### Multi-Agent Design

The agents are not separate chatbots. They are deterministic workflow roles:

- StateAgent validates and normalizes state.
- SceneRouterAgent selects a Decision Skill.
- RetrievalAgent fetches graph and strategy evidence.
- RiskAgent detects deck/run risks.
- SkillScoringAgent scores candidates.
- CriticAgent checks illegal or stale recommendations.
- ExplainerAgent returns structured reasons and UI-ready explanations.

This is interview-friendly because each agent has a concrete responsibility, observable trace, and failure mode.

### Skill System

Decision Skills make the system extensible. A card reward, shop screen, Boss relic choice, and combat turn do not share the same scoring logic, but they share the same interface. This lets new skills be added without rewriting the agent workflow.

### Harness Value

The harness is the strongest engineering signal:

- Replay Harness reproduces real Mod payloads.
- Eval Harness measures fixed labeled cases.
- Ablation Harness shows the effect of graph, strategy, risk, and critic components.
- Latency Harness tracks P50/P95/P99.
- Replay analysis flags low top separation, skip ranking, captured-vs-replay drift, and critic warnings.
- Baseline insights compare input-order and base-value policies against the full Multi-Agent Decision Harness.
- Agent trace audit expands representative cases into State, Router, Retrieval, Risk, Scoring, Critic, and Explainer steps.

This turns subjective "the recommendation feels wrong" feedback into reproducible debugging data.

## Current Metrics

| Metric | Value |
| --- | ---: |
| Graph entities | 666 |
| Graph relationships | 1442 |
| Fixed eval cases | 54 |
| Tracked archetypes | 20 |
| Chinese localization coverage | 91.5% |
| Missing relationship provenance | 0 |
| Local P95 latency | about 2-3 ms |

## Honest Limitations

- Evaluation is still curated and should expand to 200+ human-labeled real-game cases.
- Event decisions are not implemented yet.
- Map capture is conservative in the Java Mod because earlier live map state caused instability.
- Combat recommendations are shallow and should eventually use deeper search.
- Strategy knowledge is seeded and traceable, but not yet a complete expert-policy model.

## Stronger Future Version

The next high-value version should add:

- More real captured payloads from full runs.
- Human labels for high-level card, relic, shop, and Boss relic choices.
- A tuning report showing recommendation changes before and after calibration.
- More community-derived archetype rules with source URLs and confidence scores.
- A short demo GIF/video showing Mod launch, F11 archetype selection, candidate badges, and replay report.

## 中文简历压缩版

**《杀戮尖塔》实时游戏内 Multi-Agent 决策助手**
基于 Java Mod + FastAPI 接入真实游戏状态，使用 LangGraph 编排 State/Router/Retrieval/Risk/Scoring/Critic/Explainer 多 Agent 工作流，结合 Neo4j GraphRAG、本地降级缓存与可插拔 Decision Skills 输出卡牌、遗物、商店、战斗等场景推荐；实现游戏内评分 Badge、hover 解释、中英文切换、目标流派选择和 Debug 面板，并搭建 replay/eval/ablation/latency harness 量化推荐准确率、P95 延迟、无推荐率和失败原因。

可拆成两条：

- **AI 应用开发版**：强调 Mod 接入、FastAPI 服务、LangGraph Agent、GraphRAG、Skill System、低延迟 deterministic scoring、回放与评测 Harness。
- **AI 产品经理版**：强调从网页 Demo 转为游戏内 Mod 的产品判断、竞品拆解、MVP 优先级、双语交互、目标流派、失败可见性和推荐质量指标闭环。
