# 真实 Payload 到评测集的工作流

## 目标

这个工作流把“我在游戏里觉得推荐不准”转成可复现、可标注、可评测的数据。它是项目从 Demo 走向真实 AI 应用的关键闭环。

核心原则：

- 真实 Mod payload 先进入候选评测集，不直接合并进正式 eval。
- 机器推荐只能作为初始标签，必须标记为 `machine_seeded_needs_human_review`。
- 人工确认后，才能改为 `human_labeled` 并进入正式指标。

## 1. 开启真实采集

启动游戏前设置环境变量：

```powershell
$env:STS_AGENT_CAPTURE="true"
$env:STS_AGENT_CAPTURE_DIR="D:\Project\slay the spire engine\artifacts\mod_payloads"
```

也可以用 JVM 参数：

```text
-Dsts.agent.capture=true
-Dsts.agent.captureDir=D:\Project\slay the spire engine\artifacts\mod_payloads
```

采集文件是 JSONL，每条推荐记录包含：

- 当前 screen。
- query_type。
- 候选 options。
- 当前 state。
- response_summary。
- 错误信息。

## 2. 回放真实 Payload

先确认采集文件能 replay：

```powershell
.\.venv\Scripts\python.exe scripts\replay_mod_payloads.py artifacts\mod_payloads\YOUR_CAPTURE.jsonl --json
```

如果 replay 失败，优先修状态解析、候选项提取或后端推荐，而不是直接做人工标注。

## 3. 导入候选评测集

把采集文件转成候选 eval cases：

```powershell
.\.venv\Scripts\python.exe scripts\import_captured_payloads.py artifacts\mod_payloads\*.jsonl `
  --output data\captured_eval_candidates.json `
  --report-json reports\captured_payload_import_report.json `
  --report-md reports\captured_payload_import_report.md
```

没有真实采集文件时，脚本会回退到 `data/mod_payload_replay_sample.jsonl`，用于 smoke test。

## 4. 人工标注

打开 `data/captured_eval_candidates.json`，逐条检查：

- `expected_top`：机器 replay 推荐的第一名。
- `acceptable`：可以接受的 Top-N 选项。
- `metadata.replay_top`：回放时推荐的展示名。
- `metadata.score_gap`：Top1 和 Top2 的分差。
- `metadata.skip_rank`：跳过卡牌的排名。
- `metadata.quality_flags`：低区分度、推荐变化、critic warning 等。
- `metadata.top_reasons`：系统认为推荐合理的原因。

人工确认后：

```json
"label_status": "human_labeled"
```

如果机器推荐不对，修改：

```json
"expected_top": "correct_option_id",
"acceptable": ["correct_option_id", "other_acceptable_id"]
```

## 5. 进入正式评测

有两种方式：

### 方式 A：单独评测真实 payload cases

```powershell
.\.venv\Scripts\python.exe scripts\decision_harness.py --mode eval --eval data\captured_eval_candidates.json
```

适合还在积累数据时使用。

### 方式 B：合并到正式 eval

将 `human_labeled` 的 case 合并进 `data/public_eval_cases.json`，再跑：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev_check.ps1
```

适合 case 已经稳定、不会频繁改标签时使用。

## 6. 报告解读

`reports/captured_payload_import_report.md` 会显示：

- 输入文件。
- 原始记录数量。
- 导入 case 数量。
- query_type 覆盖。
- screen 覆盖。
- quality flags。
- review priority。

高优先级 review 通常包括：

- `low_top_separation`：推荐区分度低。
- `captured_top_changed`：当前 replay 结果和采集时结果不同。
- `critic_warning`：CriticAgent 发现潜在问题。
- `skip_available_but_low_rank`：有 skip 但排名靠后，需要人工判断是否合理。

## 7. 简历价值

AI 应用开发：

> 设计真实 Mod payload 到 eval candidates 的导入流程，将在线使用问题转化为可 replay、可人工标注、可消融评测的 regression cases。

AI 产品经理：

> 将用户主观反馈“推荐不准”拆解为候选项、分差、跳过排名、错误原因和人工标签，形成推荐产品质量闭环。
