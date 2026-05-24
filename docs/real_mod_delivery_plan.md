# Real Mod Delivery Plan

This plan turns the current Agentic GraphRAG prototype into a practical Slay the Spire 1 companion that uses traceable real data and can run against live game state.

## Final Target

Deliver two working surfaces backed by the same recommendation engine:

1. **Web Overlay Companion**
   - A browser overlay or packaged desktop window.
   - Receives live game state through the local FastAPI bridge.
   - Best for demos, debugging, evaluation, and portfolio presentation.

2. **Game Mod Integration**
   - A ModTheSpire/BaseMod or CommunicationMod-compatible bridge.
   - Sends current game state and active choices to `POST /mod/recommend`.
   - Initially displays recommendations in the web overlay.
   - Later optionally renders a compact in-game panel.

The AI recommendation logic stays in Python. The game-side Mod should remain thin: read state, send JSON, render concise output.

## Non-Negotiable Quality Bar

- No mock-only data in final demos.
- Every entity has provenance: source URL, extraction method, version, confidence.
- Strategy relationships are labeled separately from raw game facts.
- The app still returns useful recommendations when Neo4j or an LLM is unavailable.
- The live bridge can be tested without launching the game.
- The Mod path has clear installation and troubleshooting docs.

## Phase 0: Stabilize Runtime

**Goal:** Make the project easy to install and run on a fresh Windows machine.

Tasks:

- Add a pinned Python runtime recommendation, preferably Python 3.11 or 3.12.
- Create `.venv` setup instructions.
- Add a one-command dependency check script.
- Fix current missing dependency issues such as `anyio`.
- Add `scripts/dev_check.py` to verify imports, data files, API app import, and script entrypoints.
- Add a `Makefile` or PowerShell task file for common commands.

Acceptance criteria:

- `python -m compileall api sts_engine scripts` passes.
- `uvicorn api.main:app --reload` starts successfully.
- `http://127.0.0.1:8000/health` returns `status: ok`.
- README setup works from a clean clone.

Estimated time: 1 to 2 days.

## Phase 1: Real Data Layer

**Goal:** Replace demo assumptions with traceable Slay the Spire 1 data.

Data categories:

- Cards for all characters.
- Relics.
- Potions.
- Enemies, elites, bosses.
- Events.
- Shops and shop actions.
- Map node types.
- Keywords and mechanics.
- Character starter decks.
- Upgrade changes.

Data sources:

- Public wiki pages.
- Public community-maintained data where license allows use.
- Optional local game-derived validation if the user owns the game files.
- Human-curated strategy rules stored separately under `data/strategy`.

Implementation tasks:

- Strengthen `scripts/import_public_wiki.py`.
- Add `scripts/data_provenance_report.py`.
- Add field-level validation for `id`, `name`, `source`, `confidence`, `patch_version`.
- Split raw game facts from strategic relationships.
- Add duplicate-name and off-class validation.
- Add source coverage reports per entity type.

Acceptance criteria:

- Data report shows counts for every entity type.
- Every entity has stable English `id`.
- Every non-derived entity has a source field.
- Strategy rules never overwrite raw facts.
- CI-style validation fails on missing ids, duplicate ids, invalid references, and missing sources.

Estimated time: 4 to 7 days.

## Phase 2: Knowledge Graph and Retrieval

**Goal:** Make graph retrieval meaningful and inspectable.

Graph schema:

- Nodes: `Card`, `Relic`, `Potion`, `Enemy`, `Boss`, `Elite`, `Event`, `Mechanic`, `Archetype`, `Risk`, `Action`.
- Relationships: `APPLIES`, `SCALES_WITH`, `ENHANCES`, `COUNTERS`, `PUNISHES`, `GOOD_AGAINST`, `RISKY_WHEN`, `CORE_PIECE_FOR`, `SOLVES`.

Implementation tasks:

- Add graph schema documentation with examples.
- Add import validation before writing to Neo4j.
- Keep local fallback graph for offline operation.
- Add query fixtures for common cases:
  - poison deck card reward
  - no AoE before Act 2 elites
  - strength deck scaling
  - frost focus defense
  - shop removal decisions

Acceptance criteria:

- Neo4j import succeeds from public data.
- Local fallback returns the same top graph evidence for key fixtures.
- Graph evidence is visible in API responses and UI.
- Broken references fail validation.

Estimated time: 3 to 5 days.

## Phase 3: Recommendation Engine

**Goal:** Make recommendations explainable, stable, and not dependent on LLM guessing.

Decision types:

- Card reward.
- Relic choice.
- Shop decision.
- Route/pathing.
- Combat advice.

Scoring layers:

- Legality filter: class, screen type, invalid choices.
- Baseline value model.
- Deck synergy from graph retrieval.
- Risk coverage: no AoE, no scaling, low defense, low damage, low HP, elite risk.
- Act and floor context.
- Boss and elite matchup context.
- Optional LLM explanation only after structured scoring.

Implementation tasks:

- Expand `sts_engine/scoring.py` by decision type.
- Add separate modules for risk detection and feature extraction.
- Add confidence calibration based on evidence quality.
- Add deterministic sorting for tied scores.
- Add structured reasons and risks for every output.

Acceptance criteria:

- Recommendation still works with no LLM configured.
- Each candidate returns score, confidence, reasons, risks, and evidence.
- Invalid/off-class options are penalized or rejected.
- P95 non-LLM recommendation latency is below 500ms locally.

Estimated time: 1 to 2 weeks.

## Phase 4: Evaluation

**Goal:** Prove the system is not just a nice-looking demo.

Evaluation set:

- 200+ labeled scenarios.
- Mix of card rewards, relics, shops, pathing, and combat.
- Scenarios include character, act, floor, deck, relics, potions, boss, candidate options.
- Labels include top choice, acceptable choices, and explanation.

Baselines:

- Rule-only.
- Vector RAG.
- GraphRAG + scoring.
- LLM-only, if an external API is configured.

Metrics:

- Top-1 accuracy.
- Top-3 accuracy.
- Mean latency.
- P95 latency.
- Failure categories.
- LLM call reduction.

Acceptance criteria:

- `scripts/evaluate.py` reports metrics for all baselines.
- Evaluation cases are versioned.
- Failures are exported for review.
- README includes measured results, not placeholder claims.

Estimated time: 1 to 2 weeks.

## Phase 5: Live Web Overlay

**Goal:** Make the overlay usable during a real run.

Implementation tasks:

- Keep compact overlay mode.
- Add auto-reconnect WebSocket behavior.
- Add current decision type and candidate display.
- Add “last updated” timestamp.
- Add low-distraction visual priority:
  - top recommendation
  - key reason
  - risk warning
  - secondary options
- Add a packaged desktop option later with Tauri or Electron if browser overlay is awkward.

Acceptance criteria:

- `scripts/bridge_demo_player.py --delay 3 --loops 1` updates the overlay in realtime.
- Overlay can be kept narrow beside the game.
- LLM/Neo4j downtime does not blank the UI.

Estimated time: 3 to 5 days.

## Phase 6: Mod Bridge

**Goal:** Read real game state and send it to the backend.

Recommended path:

1. **CommunicationMod-style external bridge**
   - Fastest live-state proof.
   - Sends JSON snapshots to `/mod/recommend`.
   - Uses web overlay for display.

2. **Thin Java BaseMod bridge**
   - Reads game objects directly.
   - Sends normalized state to local FastAPI.
   - Still uses web overlay first.

3. **Native in-game panel**
   - Optional final polish.
   - Displays only top recommendation and risk notes.

State to capture:

- Class, ascension, act, floor.
- HP, max HP, gold, energy.
- Deck, upgrades, relics, potions.
- Current screen type.
- Card/relic/shop/path choices.
- Combat hand, draw pile, discard pile.
- Enemies, HP, block, intent, buffs/debuffs.
- Boss and map options where available.

Acceptance criteria:

- A real game run can trigger `/mod/recommend`.
- Overlay changes when card reward/shop/combat state changes.
- If the backend is offline, the Mod fails gracefully without crashing the game.
- Bridge logs payload and response errors for debugging.

Estimated time:

- External bridge: 3 to 5 days.
- Java BaseMod state bridge: 1 to 2 weeks.
- Native in-game panel: 1 to 2 additional weeks.

## Phase 7: Combat Advice

**Goal:** Provide useful current-turn recommendations, not only macro decisions.

Scope:

- Start with shallow search and rules.
- Avoid claiming perfect play.
- Cover common practical cases:
  - lethal detection
  - block deficit
  - potion usage
  - AoE priority
  - enemy intent response
  - boss-specific warnings

Implementation tasks:

- Add combat state parser.
- Add action sequence scorer.
- Add energy and card effect approximations.
- Add top 3 play sequences with expected damage/block/risk.

Acceptance criteria:

- Combat advice works for 30+ curated combat fixtures.
- Advice includes uncertainty when card effects are approximated.
- No recommendation is given if required combat fields are missing.

Estimated time: 2 to 4 weeks.

## Phase 8: Packaging and Portfolio Delivery

**Goal:** Make the project understandable to recruiters and usable by someone else.

Deliverables:

- README with architecture diagram.
- Demo GIF/video.
- Data provenance report.
- Evaluation report.
- Mod bridge install guide.
- Troubleshooting guide.
- Example API requests.
- Resume bullets with measured numbers only.

Acceptance criteria:

- Fresh clone setup works.
- Demo can be reproduced from documented commands.
- Metrics in README come from current evaluation output.
- GitHub repo has clear branches:
  - `main`: stable web overlay and engine
  - `codex/sts-mod-integration`: Mod bridge development
  - optional `codex/native-mod-ui`: Java native panel

Estimated time: 3 to 5 days after core work is stable.

## Practical Timeline

Minimum practical version:

- Runtime stabilization: 1 to 2 days.
- Real data validation: 4 to 7 days.
- Recommendation improvements: 1 week.
- Web overlay polish: 3 to 5 days.
- External Mod bridge: 3 to 5 days.
- Evaluation set: 1 week.

Total: about 4 to 6 focused weeks.

Stronger portfolio version:

- Add Java BaseMod bridge and native panel.
- Add larger evaluation and combat advice.

Total: about 8 to 12 focused weeks.

## Main Risks

- Mod environment friction on Windows.
- CommunicationMod payload shape may differ from sample assumptions.
- Public wiki data may be incomplete or inconsistent.
- Combat advice can become too large if full game simulation is attempted.
- Strategy relationships are inherently interpretive, so they must be labeled as curated and evaluated.

## Immediate Next Step

Stabilize the runtime first. The current environment has shown missing FastAPI transitive dependencies such as `anyio`, so the next implementation step should be:

1. Add a reproducible Python environment setup.
2. Add `scripts/dev_check.py`.
3. Verify `uvicorn api.main:app --reload` and `/health`.
4. Only then continue deeper Mod integration.
