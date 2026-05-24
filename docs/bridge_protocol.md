# Game State Bridge Protocol

This protocol is the contract between a Slay the Spire Mod/CommunicationMod-style bridge and the Python recommendation service.

The bridge is intentionally simple:

```text
Game / Mod
  -> POST /mod/state
  -> POST /get_recommendation
  -> UI overlay or companion window renders the response
```

For game-integration code, prefer the one-shot endpoint:

```text
Game / Mod
  -> POST /mod/recommend
  -> UI overlay or in-game panel renders the response
```

## Endpoint: `POST /mod/state`

Use this endpoint whenever the game state changes: entering a card reward screen, opening shop, choosing a route, starting combat, drawing cards, or enemy intent changes.

Minimal payload:

```json
{
  "run_id": "mod_live",
  "character_class": "silent",
  "ascension_level": 20,
  "act": 2,
  "current_floor": 21,
  "current_hp": 44,
  "max_hp": 70,
  "gold": 110,
  "energy": 3,
  "deck": ["Strike", "Defend", "Deadly Poison", "Bouncing Flask"],
  "upgraded_cards": [],
  "relics": ["Snecko Skull"],
  "potions": [],
  "hand_cards": [],
  "draw_pile": [],
  "discard_pile": [],
  "enemies": [],
  "combat_state": {},
  "map_options": [],
  "boss": "The Champ"
}
```

Response:

```json
{
  "message": "Mod state accepted",
  "run_id": "mod_live",
  "state": { "...": "..." }
}
```

## Endpoint: `POST /get_recommendation`

Use this endpoint when the bridge has a decision to evaluate.

Card reward:

```json
{
  "run_id": "mod_live",
  "query_type": "card_pick",
  "options": ["Catalyst", "Backflip", "Dagger Spray"],
  "user_query": "Card reward after combat."
}
```

## Endpoint: `POST /mod/recommend`

Use this endpoint from a Java Mod or bridge process when you want the lowest-friction integration. It accepts the current game snapshot and active decision in one request.

```json
{
  "state": {
    "run_id": "mod_live",
    "character_class": "silent",
    "ascension_level": 20,
    "act": 2,
    "current_floor": 21,
    "current_hp": 44,
    "max_hp": 70,
    "gold": 110,
    "energy": 3,
    "deck": ["Strike", "Defend", "Deadly Poison", "Bouncing Flask"],
    "relics": ["Snecko Skull"],
    "potions": []
  },
  "query_type": "card_pick",
  "options": ["Catalyst", "Corpse Explosion", "Backflip"],
  "user_query": "Card reward after combat."
}
```

Response:

```json
{
  "message": "Mod recommendation generated",
  "run_id": "mod_live",
  "state": { "...": "..." },
  "recommendation": { "...": "RecommendationResponse" }
}
```

The endpoint also broadcasts both `state_updated` and `recommendation` WebSocket events, so the web overlay updates from a single bridge request.

Local verification:

```powershell
python scripts\check_live_bridge.py --data data\public_full_data.json
```

The check starts a temporary API server, subscribes to `/ws`, posts one bridge scenario to `/mod/recommend`, and fails if the overlay event stream does not receive both state and recommendation updates.

Shop:

```json
{
  "run_id": "mod_live",
  "query_type": "shop",
  "options": ["Remove a Card", "Buy Potion", "Skip"],
  "user_query": "Shop decision."
}
```

Pathing:

```json
{
  "run_id": "mod_live",
  "query_type": "pathing",
  "options": ["Elite", "Rest Site", "Shop"],
  "user_query": "Choose the next map node."
}
```

Response:

```json
{
  "recommendation": "catalyst",
  "reasoning": "Recommended: Catalyst ...",
  "option_scores": [
    {
      "option_id": "catalyst",
      "name": "Catalyst",
      "score": 100.0,
      "confidence": 0.84,
      "reasons": ["Poison payoff is premium once the deck already applies Poison."],
      "risks": [],
      "evidence": []
    }
  ],
  "graph_context": [],
  "risk_report": {},
  "latency_ms": 0.2,
  "backend": "neo4j_or_local_fallback"
}
```

## Query Types

- `card_pick`: card reward or transformed card choice.
- `relic_pick`: boss chest, relic reward, or relic choice.
- `shop`: shop buy/remove/potion decision.
- `pathing`: route/map node selection.
- `combat`: current-turn combat advice.

## Mod Implementation Notes

- Keep game-facing card names as English display names first; the backend resolves both IDs and names.
- Send the full deck/relic/potion state on every update. The API treats `/mod/state` as a snapshot, not a patch.
- For combat, include enemy intents and current hand when available. The current recommender has only shallow combat support, but this keeps the protocol forward compatible.
- A desktop overlay can subscribe to `ws://127.0.0.1:8000/ws` to receive state and recommendation updates in realtime.

Minimal combat payload fields:

```json
{
  "query_type": "combat",
  "state": {
    "character_class": "silent",
    "energy": 3,
    "hand_cards": ["Neutralize", "Survivor", "Strike", "Dagger Spray", "Defend"],
    "potions": ["Block Potion"],
    "enemies": [
      {"name": "Blue Slaver", "hp": 13, "intent": "attack", "intent_damage": 12},
      {"name": "Red Slaver", "hp": 33, "intent": "attack", "intent_damage": 8}
    ],
    "combat_state": {"incoming_damage": 20}
  }
}
```

The first combat implementation is intentionally shallow: it estimates damage/block from known hand cards, prioritizes legal energy-bounded play sequences, and only promotes potion use when incoming damage is meaningfully dangerous.

## CommunicationMod-Style Adapter

This repository includes a thin adapter for state snapshots shaped like an external CommunicationMod bridge:

```powershell
python scripts\communication_mod_adapter.py --state-file data\communication_mod_sample_state.json
```

The adapter accepts common bridge fields such as `class`, `floor`, `choice_list`, `screen_type`, and `monsters`, then normalizes them into `/mod/state`.

By default the adapter uses `/mod/recommend`. Pass `--legacy-two-step` to use `/mod/state` followed by `/get_recommendation`.

Use it as the first integration step before investing in a native BaseMod in-game UI.
