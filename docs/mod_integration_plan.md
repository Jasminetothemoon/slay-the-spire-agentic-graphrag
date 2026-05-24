# Slay the Spire Mod Integration Plan

This branch keeps the web overlay intact while adding the fastest path toward real game-state integration.

## Two Deliverable Modes

### 1. Web Overlay Companion

This remains the default demo path:

```text
Game state source -> FastAPI /mod/state -> WebSocket -> browser overlay
```

Use this when you want a reliable portfolio demo:

- No Java build environment required.
- Works with manual JSON, simulator scenarios, or a future Mod bridge.
- The overlay can sit beside the game window and update in realtime.

### 2. In-Game Mod Bridge

This branch starts with a lightweight external bridge and leaves room for a full BaseMod UI later:

```text
CommunicationMod or Java bridge -> local FastAPI -> recommendation -> overlay or in-game panel
```

The first milestone is state ingestion, not native rendering. Native in-game rendering should come after the recommender and state protocol are stable.

## Adapter Script

`scripts/communication_mod_adapter.py` converts a CommunicationMod-style JSON snapshot into this project's `/mod/state` contract.

Run with a local FastAPI service:

```powershell
uvicorn api.main:app --reload
python scripts\communication_mod_adapter.py --state-file data\communication_mod_sample_state.json
```

The adapter:

- Normalizes class names such as `THE_SILENT` to `silent`.
- Converts `floor` to `current_floor`.
- Converts `choice_list`, `choices`, `cards`, `relic_choices`, or `shop_items` into recommendation options.
- Infers query type from `screen_type`, for example `CARD_REWARD -> card_pick`.
- Posts the normalized snapshot to `/mod/state`.
- Optionally calls `/get_recommendation`.

To post only state:

```powershell
python scripts\communication_mod_adapter.py --state-file data\communication_mod_sample_state.json --no-recommend
```

## Why This Split Helps

The web overlay is the fastest and most stable demonstration surface. The Mod bridge proves the project can read real game state. Keeping them separate avoids blocking the AI application demo on Java UI complexity.

Recommended order:

1. Keep polishing `main` as the portfolio-ready web overlay.
2. Use this branch to validate real game-state ingestion.
3. Once the state payload is stable, add a Java BaseMod panel that renders only the top recommendation and risk notes.

## Future Native Mod UI

A native BaseMod/ModTheSpire implementation should stay thin:

- Subscribe to relevant game events.
- Collect deck, relics, potions, hand, enemies, intent, and screen choices.
- POST snapshots to `http://127.0.0.1:8000/mod/state`.
- POST choices to `http://127.0.0.1:8000/get_recommendation`.
- Render a compact recommendation panel in-game.

The Java Mod should not own the recommendation algorithm. That logic stays in Python, where GraphRAG, scoring, evaluation, and LLM explanation are easier to iterate.
