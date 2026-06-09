# 游戏内 Mod 助手说明

本项目的主产品形态改为原生游戏内 Mod 助手。网页端只作为调试、回放和评测展示使用，玩家不需要通过网页手动同步状态或获取推荐。

## 游戏内交互

- `F8`：隐藏或显示推荐面板。
- `F9`：展开或收起 Debug 信息。
- 常驻推荐面板会显示：
  - 当前场景，例如 Card Reward、Relic Reward、Boss Relic、Shop、Map、Combat。
  - Top 推荐。
  - `grade / score` 徽章，例如 `A 84`。
  - 置信度、主要理由、主要风险。
- Debug 面板会显示：
  - 当前 screen。
  - query type。
  - options 数量。
  - top recommendation。
  - 请求延迟。
  - 最近错误。

## 后端 Mod 接口

Java Mod 继续使用：

```text
POST /mod/recommend
```

推荐响应增加了面向游戏内 UI 的字段：

- `scene_type`
- `option_scores[].grade`
- `option_scores[].display_badge`
- `option_scores[].score_breakdown`
- `option_scores[].why_not`
- `debug`

后端还提供诊断接口：

```text
GET /mod/diagnostics
```

该接口返回最近 20 次 Mod 请求、最后错误、当前 run、scene、query type 和 options 数量。

## 真实 Payload 采样

默认不写采样日志。需要采样真实游戏 payload 时，启动游戏前设置：

```powershell
$env:STS_AGENT_CAPTURE = "true"
$env:STS_AGENT_CAPTURE_DIR = "D:\Project\slay the spire engine\artifacts\mod_payloads"
```

也可以使用 Java system properties：

```text
-Dsts.agent.capture=true
-Dsts.agent.captureDir=D:\Project\slay the spire engine\artifacts\mod_payloads
```

采样文件为 JSONL，每行记录一次状态或推荐事件，包含：

- request payload
- Java screen
- query type
- options count
- response summary
- error

## Replay

采样后可以用 replay 脚本复现推荐：

```powershell
.\.venv\Scripts\python.exe scripts\replay_mod_payloads.py artifacts\mod_payloads\YOUR_CAPTURE.jsonl --json
```

内置 fixture 可用于检查脚本是否正常：

```powershell
.\.venv\Scripts\python.exe scripts\replay_mod_payloads.py data\mod_payload_replay_sample.jsonl --json
```

## 当前验收重点

- 不打开网页也能在游戏内看到推荐和失败原因。
- API 关闭时，游戏内必须显示连接错误。
- 进入卡牌奖励、遗物奖励、Boss 遗物、商店、地图、战斗时，scene type 必须正确。
- Debug 面板必须能显示最近一次请求的 query type 和 options 数量。
- 真实游戏 payload 必须能被 JSONL 采样并通过 replay 脚本复现。
