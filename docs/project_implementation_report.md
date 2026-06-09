# 项目实施精华报告

## 一句话总结

本项目从最初的《杀戮尖塔》GraphRAG 网页 Demo，逐步升级为一个 **Mod-first Multi-Agent Decision Harness**：通过游戏内 Mod 自动读取真实局面，在本地 AI 推荐服务中完成状态解析、图谱检索、风险识别、Skill 评分、Critic 校验和结构化解释，最终把推荐直接显示在游戏界面中。

## 项目为什么有价值

这个项目的价值不在于“做了一个游戏助手”，而在于它把 AI 应用开发中常见的难点放进了一个可演示、可评测、可复现的复杂环境：

- 状态复杂：卡组、遗物、药水、敌人、路线、商店、流派目标都会影响决策。
- 决策依赖上下文：同一张卡在不同职业、流派、Act、血量和卡组结构中价值不同。
- 体验要求实时：玩家不能等待 LLM 慢慢生成答案。
- 错误需要可见：如果推荐错了，必须知道是状态采集、检索、评分还是 UI 匹配出问题。
- 质量需要评测：不能只说“感觉更准”，要能 replay、ablation、latency 和人工 case 验证。

## 技术架构演进

### 第一阶段：从 GraphRAG Demo 到可运行服务

最初的思路是用 Neo4j 建立游戏实体知识图谱，再通过 GraphRAG 给出建议。这个方向有技术亮点，但如果只停留在网页上输入状态、输出解释，很容易变成普通 RAG Demo。

关键调整：

- 保留 Neo4j/GraphRAG 作为知识与关系检索层。
- 增加本地 JSON fallback，保证 Neo4j 不可用时仍可演示。
- 将推荐从“LLM 拍板”改为“结构化评分 + LLM 可选解释”，降低延迟和不稳定性。

### 第二阶段：从网页助手转向游戏内 Mod

用户反馈指出：网页可用性不足，真实游戏中切屏成本很高。因此项目重心改成原生 Mod。

解决方案：

- 用 Java ModTheSpire/BaseMod bridge 读取当前游戏状态。
- 通过 FastAPI `/mod/state` 和 `/mod/recommend` 与本地推荐服务通信。
- 在游戏内右上角显示推荐面板。
- 增加 F8/F9/F10/F11：
  - F8 显示/隐藏推荐。
  - F9 显示 Debug。
  - F10 中英文切换。
  - F11 切换目标流派。
- 在卡牌、遗物、商店候选项旁显示评分 Badge 和 hover 解释。

这个阶段的核心产品判断是：**网页端只做调试台，游戏内 Mod 才是主产品**。

### 第三阶段：从评分函数升级为 Multi-Agent + Skill System

为了避免项目被看成“几个 if else 规则”，系统被拆成两层：

- LangGraph 多 Agent 工作流。
- 可插拔 Decision Skills。

当前 Agent 角色：

- `StateAgent`：归一化状态，识别 run、职业、楼层、场景。
- `SceneRouterAgent`：根据场景选择 Skill。
- `RetrievalAgent`：检索图谱、流派规则和策略上下文。
- `RiskAgent`：识别缺 AoE、低血量、缺防御、输出不足、商店风险等。
- `SkillScoringAgent`：调用对应 Skill 给候选项评分。
- `CriticAgent`：检查非法候选、场景错配、旧推荐残留。
- `ExplainerAgent`：生成 UI 可展示的理由、风险、why_not 和 debug 信息。

当前 Decision Skills：

- `CardPickSkill`
- `RelicPickSkill`
- `ShopSkill`
- `PathingSkill`
- `CombatSkill`
- `RestSiteSkill`

这样设计以后，面试时可以清楚说明：多 Agent 不是为了形式，而是为了把真实推荐链路拆成可观测、可测试、可替换的工作流节点。

## 关键困难与解决方式

### 困难 1：网页助手不符合真实使用场景

问题：

玩家在游戏中不愿意频繁切到网页点击同步和获取推荐。即使后端推荐正确，产品体验也不成立。

解决：

- 将核心体验转为游戏内 Mod。
- 网页端降级为调试、评测和展示。
- 推荐框、候选项 Badge、hover 解释直接渲染在游戏内。

思考：

AI 产品不能只看模型能力，还要看它嵌入用户流程的位置。如果用户必须改变行为习惯才能使用，MVP 的价值会大幅下降。

### 困难 2：真实游戏状态同步不稳定

问题：

脚本测试通过，不代表真实游戏中可用。曾出现游戏加载崩溃、地图场景 500、奖励场景仍残留战斗推荐等问题。

解决：

- 增加 `/mod/diagnostics` 和游戏内 Debug 面板。
- 每次请求记录 scene、query_type、options_count、latency、error。
- 增加 JSONL capture/replay，把实机 payload 保存下来复现。
- 对不稳定的地图 live capture 暂时保守关闭，后端 PathingSkill 继续通过 harness 保留。

思考：

实时 AI 应用最怕“现场才坏”。Replay harness 的意义是把一次用户现场错误转成可重复的测试 case。

### 困难 3：推荐不够像高端玩家

问题：

单纯按卡牌强度或泛化规则排序，会导致推荐区分度低，也无法处理“跳过卡牌”或“特定流派才需要”的情况。

解决：

- 增加目标流派选择，玩家可以在开局或中途用 F11 切换。
- 策略层追踪 20 个核心 archetype。
- 对卡牌、遗物、商店、Boss 遗物分别写入不同 Skill。
- 推荐输出增加 score breakdown、risks、why_not、skip rank、low_top_separation 等字段。

思考：

高手策略不是一个全局 tier list，而是“当前局面 + 未来风险 + 卡组方向 + 候选项机会成本”的综合判断。

### 困难 4：中英文和游戏内 UI 容易失控

问题：

英文文本过长会溢出面板；切中文后有些卡牌名、战斗顺序仍显示英文；中英文重叠会影响游戏内阅读。

解决：

- 增加 F10 中英文切换。
- 增加中文 localization 数据。
- 对推荐面板做更紧凑的排版和换行。
- 将展示字段和内部英文 id 分离，避免中文名影响匹配逻辑。

思考：

AI 应用的可用性不只在模型答案，还包括文本长度、语言一致性、错误状态和用户能不能在压力场景中快速读懂。

### 困难 5：Agent 和 GraphRAG 容易被质疑“只是包装”

问题：

AI 实习面试常问多 Agent、Skill、Harness。如果项目只说“用了 LangGraph 和 Neo4j”，含金量不足。

解决：

- 把 Agent 定义成真实职责节点，并输出 `agent_trace`。
- 把推荐能力拆成 Decision Skills，每个场景独立评分。
- 增加 CriticAgent 做合法性和场景一致性检查。
- 建立 replay/eval/ablation/latency harness，验证每个模块的贡献。

思考：

工程项目里的 Agent 价值不在“像人一样聊天”，而在于把复杂流程拆成可观测、可回放、可评测、可替换的决策链路。

## Neo4j 与 NetworkX 的取舍

选择 Neo4j 的原因：

- 需要持久化存储实体、关系、来源、置信度和版本。
- 需要用 Cypher 做多跳查询，例如卡组缺 AoE、下一层有群怪风险、哪些牌能覆盖风险。
- 需要可解释证据链，方便把图谱关系展示给用户和面试官。
- 后续可以独立部署图数据库，而不是把图结构锁在进程内存里。

NetworkX 更适合：

- 离线分析。
- 小规模算法实验。
- 图算法原型验证。

本项目不是算法实验，而是本地应用服务和可解释推荐系统，所以 Neo4j 更贴近最终形态。同时保留本地 JSON fallback，保证演示稳定性。

## 为什么实时链路不调用外部 LLM

实时推荐链路当前不调用外部 LLM，这是一个有意设计：

- 降低延迟，推荐需要在游戏中即时出现。
- 降低成本，不需要每次奖励或战斗都请求模型。
- 降低不确定性，核心推荐由可测试的 scoring 和 Skill 控制。
- 提高可回归性，同一个 payload 应得到稳定结果。

后续可以加入可选异步 LLM：

- 用于自然语言解释增强。
- 用于离线总结社区攻略。
- 用于把失败 case 归因成人类可读报告。

## 当前成果

当前项目已经具备以下可展示成果：

- 游戏内 Mod 主体验，而不是网页 Demo。
- FastAPI 本地推荐服务。
- LangGraph 多 Agent 工作流。
- 可插拔 Decision Skills。
- Neo4j GraphRAG 与本地 JSON fallback。
- 中英文显示、目标流派选择、候选项评分 Badge。
- JSONL capture/replay。
- eval/ablation/latency harness。
- 666 个实体、1442 条关系、20 个流派、54 个固定评测 case。
- 中文 localization 覆盖率约 91.5%。

## 当前限制

- 评测集仍偏小，需要扩展到 200+ 真实人工标注 case。
- 地图 live capture 曾经不稳定，当前 Mod 侧采取保守策略。
- 战斗建议还是浅层规则，尚未做深层搜索。
- 事件助手尚未完成。
- 社区策略知识已经有结构化规则，但还不是完整专家策略模型。
- 缺少正式 PRD、竞品分析和产品指标文档。

## 对 AI 应用开发方向的价值

这个项目可以证明以下能力：

- 能把 Agent/RAG 从 Notebook 或网页 Demo 落到真实客户端环境。
- 能设计低延迟本地 AI 服务。
- 能把复杂决策拆成 Skill，并通过 Agent workflow 编排。
- 能建立评测、回放、消融和延迟 Harness。
- 能处理真实工程问题：异常、降级、状态错配、UI 限制、多语言展示。

推荐简历主线：

> Java Mod + FastAPI 实时状态接入，LangGraph 多 Agent 编排，Neo4j GraphRAG 检索，可插拔 Decision Skills，Replay/Eval/Ablation/Latency Harness。

## 对 AI 产品经理方向的价值

这个项目可以证明以下能力：

- 能从用户流程痛点出发重构产品形态。
- 能基于竞品确定优先级，而不是只做技术堆叠。
- 能定义 MVP、非目标范围、指标和迭代闭环。
- 能理解 AI 系统的边界：实时性、解释性、成本、稳定性。
- 能把“推荐质量”这种主观问题转成可度量指标。

推荐简历主线：

> 将 AI 决策助手从网页 Demo 重构为游戏内 Mod-first 产品，围绕无感使用、双语展示、流派选择、失败可见性和推荐质量评测设计 MVP 与迭代指标。

## 下一步最值得投入的工作

1. 扩展真实游戏 payload 和人工标注评测集。
2. 写 PRD、竞品分析、产品指标和用户旅程。
3. 完善 baseline/ablation 报告，证明 GraphRAG、风险评估、流派规则的贡献。
4. 增加 Agent trace audit 示例，让多 Agent 协作更可展示。
5. 建立 GitHub Actions CI，提升工程可信度。
6. 加入用户反馈闭环，把玩家实际选择和系统推荐差异保存为训练/调参数据。

## 可用于面试的 60 秒讲法

我做的不是一个单纯的游戏推荐网页，而是把《杀戮尖塔》当成复杂实时决策环境，做了一个游戏内 AI 决策助手。它通过 Java Mod 读取当前局面，把状态发给本地 FastAPI 服务，再由 LangGraph 编排 State、Router、Retrieval、Risk、Scoring、Critic、Explainer 多个 Agent 节点。推荐不是让 LLM 直接拍板，而是用 Neo4j GraphRAG 和社区策略规则检索上下文，再通过不同 Decision Skill 做结构化评分，所以延迟低、结果可回放、可解释。后面我又做了 JSONL replay、固定 eval、消融和 latency harness，把“推荐准不准”变成可以评测和迭代的问题。这个项目对我来说最重要的收获是：AI 应用的难点不只是模型调用，而是产品入口、状态接入、可靠性、评测闭环和解释性。
