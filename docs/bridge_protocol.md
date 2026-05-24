# Game State Bridge Protocol

This protocol is the contract between a Slay the Spire Mod/CommunicationMod-style bridge and the Python recommendation service.

The bridge is intentionally simple:

```text
Game / Mod
  -> POST /mod/state
  -> POST /get_recommendation
  -> UI overlay or companion window renders the response
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
