# Java Mod Bridge

This is the first native ModTheSpire/BaseMod bridge for the project. It keeps the recommendation engine in Python and makes the Java side intentionally thin:

```text
Slay the Spire Java Mod
  -> collect live game state
  -> POST http://127.0.0.1:8000/mod/state or /mod/recommend
  -> parse top recommendation from the local API response
  -> render a compact in-game panel and update the web overlay through WebSocket
```

## Current Scope

Implemented in `mod-bridge`:

- ModTheSpire manifest.
- Gradle Java 8 project.
- Configurable local API URL.
- HTTP POST client with short timeouts and graceful failure.
- Live state collection for:
  - character class
  - ascension
  - act and floor
  - HP, max HP, gold, energy
  - deck and upgraded cards
  - relics and potions
  - hand, draw pile, discard pile
  - enemies, HP, block, intent, estimated incoming damage
- Automatic recommendation request for:
  - card reward screens
  - shop choices
  - combat hands
- API response parsing for the top option, score, confidence, reason, and risk.
- Compact in-game recommendation panel rendered through BaseMod `PostRenderSubscriber`.

This version keeps the browser overlay for debugging and demos, while also rendering the current top recommendation directly inside the game.

## Local Dependencies

Before building, put these jars in:

```text
mod-bridge/libs
```

Expected files:

- Slay the Spire desktop/game jar, commonly `desktop-1.0.jar`.
- `ModTheSpire.jar`.
- `BaseMod.jar`.

The jars are local dependencies and are not committed to GitHub.

## Build

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_mod_bridge.ps1
```

The repository can use a portable toolchain under `.tools` so a system-wide Java/Gradle install is not required. The script expects:

```text
.tools/jdk17
.tools/gradle
```

The output jar is created under:

```text
mod-bridge/build/libs/sts-agent-bridge-0.1.0.jar
```

## Run With The Backend

Start the Python API first:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_api.ps1
```

Open the overlay:

```text
http://127.0.0.1:8000
```

Install the built Mod jar into your Slay the Spire `mods` directory alongside BaseMod and ModTheSpire. Launch the game with ModTheSpire and enable `STS Agent Bridge`.

## Runtime Configuration

Defaults:

- API URL: `http://127.0.0.1:8000`
- run id: `mod_live`
- verbose logging: `false`

Environment variables:

```powershell
$env:STS_AGENT_API_URL = "http://127.0.0.1:8000"
$env:STS_AGENT_RUN_ID = "mod_live"
$env:STS_AGENT_VERBOSE = "true"
```

Java system properties are also supported:

```text
-Dsts.agent.apiUrl=http://127.0.0.1:8000
-Dsts.agent.runId=mod_live
-Dsts.agent.verbose=true
```

## Verification Without The Game

Run the project-level checks:

```powershell
python scripts\check_mod_bridge.py
powershell -ExecutionPolicy Bypass -File scripts\dev_check.ps1
```

Run the existing backend/overlay live path:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1 -Delay 0 -Loops 1
```

The structure check confirms that the Java bridge has the expected manifest, protocol endpoints, response parser, in-game panel, and state fields. Full Java compilation requires the local game, ModTheSpire, and BaseMod jars in `mod-bridge/libs`.

## Next Engineering Steps

- Play through card reward, shop, and combat screens to tune panel placement.
- Add relic reward extraction.
- Add map/path extraction.
- Add a hotkey or config toggle for hiding/showing the in-game panel.
- Add localized in-game panel text once CJK font rendering is verified in the game client.
