# Java Mod 桥接文档

这是项目里的第一个原生 ModTheSpire/BaseMod 桥接版本。它的设计原则是：推荐引擎仍然放在 Python 后端，Java Mod 只负责读取游戏状态、发送请求、解析结果和渲染轻量面板。

```text
Slay the Spire Java Mod
  -> 采集实时游戏状态
  -> POST http://127.0.0.1:8000/mod/state 或 /mod/recommend
  -> 从本地 API 响应中解析最高优先级推荐
  -> 在游戏内渲染紧凑推荐面板，并通过 WebSocket 更新网页悬浮窗
```

## 当前范围

`mod-bridge` 中已经实现：

- ModTheSpire manifest。
- Gradle Java 8 项目。
- 可配置的本地 API URL。
- 带短超时和失败降级的 HTTP POST 客户端。
- 实时状态采集：
  - 角色职业
  - 进阶等级
  - Act 和楼层
  - 当前 HP、最大 HP、金币、能量
  - 卡组和已升级卡牌
  - 遗物和药水
  - 手牌、抽牌堆、弃牌堆
  - 敌人、敌人 HP、格挡、意图、估算 incoming damage
  - 打开地图时的下一步路线选项
- 自动请求推荐：
  - 卡牌奖励界面
  - 普通遗物奖励界面
  - Boss 遗物奖励界面
  - 商店选择
  - 地图路线选择
  - 当前战斗手牌
- API 响应解析：最高推荐项、分数、置信度、理由和风险。
- 通过 BaseMod `PostRenderSubscriber` 渲染紧凑的游戏内推荐面板。
- 运行中按 `F8` 可以隐藏或显示游戏内推荐面板。

这个版本会同时保留浏览器网页悬浮窗，用于调试和演示；也会把当前最高推荐直接渲染到游戏内。

## 本地依赖

构建前，需要把这些 jar 放到：

```text
mod-bridge/libs
```

期望文件：

- Slay the Spire 游戏 jar，通常是 `desktop-1.0.jar`。
- `ModTheSpire.jar`。
- `BaseMod.jar`。

这些 jar 属于本地依赖，不会提交到 GitHub。

## 构建

在仓库根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_mod_bridge.ps1
```

仓库可以使用 `.tools` 下的便携工具链，因此不强制要求系统全局安装 Java/Gradle。脚本会期望以下路径存在：

```text
.tools/jdk17
.tools/gradle
```

构建产物会生成在：

```text
mod-bridge/build/libs/sts-agent-bridge-0.1.0.jar
```

## 与后端一起运行

先启动 Python API：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_api.ps1
```

打开网页悬浮窗：

```text
http://127.0.0.1:8000
```

把构建好的 Mod jar 安装到 Slay the Spire 的 `mods` 目录，并与 BaseMod、ModTheSpire 放在一起。然后通过 ModTheSpire 启动游戏，并启用 `STS Agent Bridge`。

## 运行时配置

默认配置：

- API URL：`http://127.0.0.1:8000`
- run id：`mod_live`
- verbose logging：`false`

环境变量：

```powershell
$env:STS_AGENT_API_URL = "http://127.0.0.1:8000"
$env:STS_AGENT_RUN_ID = "mod_live"
$env:STS_AGENT_VERBOSE = "true"
```

也支持 Java system properties：

```text
-Dsts.agent.apiUrl=http://127.0.0.1:8000
-Dsts.agent.runId=mod_live
-Dsts.agent.verbose=true
```

## 不启动游戏时的验证方式

运行项目级检查：

```powershell
python scripts\check_mod_bridge.py
powershell -ExecutionPolicy Bypass -File scripts\dev_check.ps1
```

运行已有的后端/网页悬浮窗 live path：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1 -Delay 0 -Loops 1
```

结构检查会确认 Java bridge 具备预期的 manifest、协议端点、响应解析器、游戏内面板和状态字段。完整 Java 编译需要本地游戏、ModTheSpire 和 BaseMod jar 已经放入 `mod-bridge/libs`。

## 游戏内验收清单

启动游戏前：

- 使用 `scripts\run_api.ps1` 启动本地 API。
- 打开 `http://127.0.0.1:8000`，测试时同步观察浏览器网页悬浮窗。
- 通过 ModTheSpire 启动 Slay the Spire，并确保 BaseMod 和 `STS Agent Bridge` 已启用。

运行过程中，检查以下场景：

- 新开局地图：在还没有选择第一层房间前打开 Act 地图，也应该能生成路线推荐。
- 卡牌奖励：面板应该显示最高推荐卡、分数、置信度、理由和风险。
- 普通遗物奖励：出现遗物奖励时，面板应该刷新为遗物推荐。
- Boss 遗物奖励：面板应该在 Boss 遗物三选一中给出推荐。
- 商店：面板应该比较可见的卡牌购买选项，并在金币足够时考虑删牌。
- 战斗：面板应该基于当前手牌给出出牌序列建议。
- 后端不可用：如果停止 API，面板应该显示本地 API 连接警告，而不是静默消失。
- 面板开关：按 `F8` 应该能隐藏/显示游戏内面板，同时不影响后端状态同步。

每个场景后记录这些观察：

- 浏览器网页悬浮窗是否收到了相同的当前状态？
- 游戏内面板是否在约 1 秒内刷新？
- 推荐结果是否对应当前界面上的合法可选项？
- 面板是否遮挡了重要的游戏 UI？

## 下一步工程任务

- 实机跑一遍卡牌奖励、商店和战斗界面，调优面板位置。
- 实机跑一遍普通遗物奖励、Boss 遗物和地图界面，调优决策签名。
- 在确认游戏客户端 CJK 字体渲染可行后，增加游戏内中文面板文本。
