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
  - next map route options when the map is open
- Automatic recommendation request for:
  - card reward screens
  - normal relic reward screens
  - boss relic reward screens
  - shop choices
  - map route choices
  - combat hands
- API response parsing for the top option, score, confidence, reason, and risk.
- Compact in-game recommendation panel rendered through BaseMod `PostRenderSubscriber`.
- `F8` toggles the in-game recommendation panel on or off during a run.

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

## In-Game Acceptance Checklist

Before launching the game:

- Start the local API with `scripts\run_api.ps1`.
- Open `http://127.0.0.1:8000` to watch the browser overlay while testing.
- Launch Slay the Spire through ModTheSpire with BaseMod and `STS Agent Bridge` enabled.

During a run, verify these scenes:

- New run map: opening the Act map should produce path recommendations even before the first room is selected.
- Card reward: the panel should show the top card, score, confidence, reason, and risk.
- Normal relic reward: the panel should refresh to a relic recommendation when a relic reward appears.
- Boss relic reward: the panel should refresh to one of the boss relic choices.
- Shop: the panel should compare visible card purchases and card removal when affordable.
- Combat: the panel should suggest a play sequence from the current hand.
- Backend unavailable: if the API is stopped, the panel should display a local API connection warning instead of silently disappearing.
- Toggle: pressing `F8` should hide/show the in-game panel without stopping backend state sync.

Record these observations after each scene:

- Did the browser overlay receive the same current state?
- Did the in-game panel update within about one second?
- Did the recommendation correspond to a legal visible choice?
- Did the panel overlap important game UI?

## Next Engineering Steps

- Play through card reward, shop, and combat screens to tune panel placement.
- Play through relic reward, boss relic, and map screens to tune decision signatures.
- Add localized in-game panel text once CJK font rendering is verified in the game client.
