# Slay the Spire Agentic GraphRAG Decision System

This project is a realtime AI decision assistant for **Slay the Spire 1**. The game is the domain, but the engineering goal is broader: build a production-shaped AI application that combines knowledge graphs, Agent workflows, structured recommendation scoring, realtime state sync, and evaluation.

## What It Does

- Models cards, relics, potions, enemies, bosses, mechanics, shops, routes, and archetypes as a knowledge graph.
- Uses GraphRAG retrieval to find multi-hop synergies and risks for the current run state.
- Uses a LangGraph workflow to validate state, retrieve graph context, assess risks, score options, and explain decisions.
- Returns structured recommendations for card picks, relic picks, shops, routes, and combat-oriented states.
- Provides a FastAPI service, WebSocket updates, and a lightweight web demo.
- Runs without Neo4j by falling back to the local JSON knowledge base; Neo4j remains the preferred graph backend for larger data.

## Architecture

```text
Game / Mod Bridge
      |
      v
FastAPI state API + WebSocket
      |
      v
LangGraph Agent Workflow
  - validate_state
  - retrieve_context
  - assess_risk
  - score_options
  - explain_decision
      |
      v
Neo4j GraphRAG or local JSON fallback
      |
      v
Structured recommendation response
```

## Project Layout

```text
api/main.py                 FastAPI app, WebSocket endpoint, mod-state ingestion stub
sts_engine/agent.py         LangGraph workflow
sts_engine/knowledge_base.py Local knowledge-base loader and graph-style lookup
sts_engine/retriever.py     Neo4j-first GraphRAG retriever with local fallback
sts_engine/scoring.py       Structured recommendation scorer
sts_engine/state.py         RunState and response types
scripts/ingest_graph.py     Neo4j ingestion
scripts/validate_data.py    Data integrity checks
scripts/evaluate.py         Recommendation evaluation harness
web/                        Lightweight demo UI
data/sample_data.json       Seed schema and curated MVP data
data/eval_cases.json        Seed evaluation cases
```

## Quick Start

Use Python 3.11 or 3.12. On Windows:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
.\scripts\dev_check.ps1
.\scripts\run_api.ps1
```

Open `http://127.0.0.1:8000` and start a demo run.

For detailed Windows setup and troubleshooting, see:

```text
docs/windows_setup.md
```

## Neo4j Ingestion

Neo4j is optional for local demos. To ingest the graph:

```bash
set NEO4J_URI=bolt://localhost:7687
set NEO4J_USER=neo4j
set NEO4J_PASSWORD=your_password
python scripts/ingest_graph.py --dry-run
python scripts/ingest_graph.py
```

## Public Wiki Data Import

The seed dataset is intentionally small. To build a larger public dataset from `slaythespire.gg`:

```bash
python scripts/import_public_wiki.py --links-only --output data/public_link_index.json
python scripts/import_public_wiki.py --collections cards --output data/public_cards.json --checkpoint-every 50
python scripts/import_public_wiki.py --output data/public_full_data.json --checkpoint-every 50
python scripts/normalize_dataset.py --input data/public_full_data.json --output data/public_full_data.json
python scripts/normalize_provenance.py --input data/public_full_data.json --output data/public_full_data.json
python scripts/validate_data.py --data data/public_cards.json
python scripts/validate_data.py --data data/public_full_data.json
python scripts/data_quality_report.py --data data/public_full_data.json
python scripts/data_provenance_report.py --data data/public_full_data.json
```

To run the app with an imported dataset instead of the seed data:

```bash
set STS_KB_PATH=data/public_cards.json
uvicorn api.main:app --reload
```

Current public import snapshot:

- 361 cards
- 146 relics
- 42 potions
- 21 elite/boss enemy entries
- 25 extracted mechanics/risk nodes

For provenance coverage and known data gaps, see:

```text
docs/data_audit.md
```

## Strategy Layer

Mechanic extraction alone is not enough for strong recommendations, so the project includes a curated strategy layer:

```text
data/strategy/archetypes.json
```

It currently covers 8 archetypes:

- Silent Poison
- Silent Shiv
- Ironclad Strength
- Ironclad Exhaust
- Defect Frost Focus
- Defect Lightning
- Watcher Stance Dance
- Watcher Wrath Burst

These rules add explicit strategy signals such as enablers, payoffs, support cards, risk coverage, and archetype-specific pick bonuses. Example: `Catalyst` is scored as a Poison payoff only when the deck already has Poison sources, while `Corpse Explosion` is recognized as a Poison deck's AoE solution.

Run public-data strategy evaluation:

```bash
python scripts/evaluate.py --data data/public_full_data.json --eval data/public_eval_cases.json
```

Track strategy coverage:

```bash
python scripts/strategy_coverage_report.py
```

The strategy layer is intentionally measured as coverage, not claimed as complete. The current coverage inventory tracks 20 archetypes across four classes; all 20 now have seeded scoring rules and evaluation signals.

## API Example

```bash
curl -X POST http://127.0.0.1:8000/start_run ^
  -H "Content-Type: application/json" ^
  -d "{\"character_class\":\"silent\",\"ascension_level\":20,\"max_hp\":70}"
```

```bash
curl -X POST http://127.0.0.1:8000/get_recommendation ^
  -H "Content-Type: application/json" ^
  -d "{\"run_id\":\"run_xxxxxxxx\",\"query_type\":\"card_pick\",\"options\":[\"Catalyst\",\"Backflip\",\"Dagger Spray\"],\"user_query\":\"Which card should I pick?\"}"
```

The response includes:

- `recommendation`
- `reasoning`
- `option_scores`
- `graph_context`
- `risk_report`
- `latency_ms`

## Game-State Bridge

The bridge protocol is documented in:

```text
docs/bridge_protocol.md
```

Run bridge scenarios without starting FastAPI:

```bash
python scripts/bridge_simulator.py --mode offline --data data/public_full_data.json
```

Run against a local API server:

```bash
set STS_KB_PATH=data/public_full_data.json
uvicorn api.main:app --reload
python scripts/bridge_simulator.py --mode http --base-url http://127.0.0.1:8000
```

The simulator posts full run-state snapshots in the same shape a future Mod/CommunicationMod bridge should send to `/mod/state`, then requests a recommendation for the active decision.

Replay bridge scenarios with a delay so the web overlay updates like a live companion:

```bash
python scripts/bridge_demo_player.py --delay 3 --loops 1
```

For Mod clients, the shortest path is the one-shot endpoint:

```text
POST /mod/recommend
```

It accepts a game-state snapshot plus the active decision options, then broadcasts both state and recommendation updates to the overlay.

## Resume-Oriented Targets

The current repository implements the MVP skeleton. The next high-value work is to scale the dataset and evaluation:

- 400+ entities and 1000+ graph relationships.
- 200+ labeled evaluation cases.
- P95 recommendation latency below 500ms for non-LLM recommendations.
- Comparison report: rules only vs pure LLM vs vector RAG vs GraphRAG + scoring.
- Mod bridge that posts live game state into `/mod/state`.

## Current Status

Implemented:

- UTF-8 schema and seed data.
- Agentic GraphRAG workflow.
- Structured scoring and explanations.
- Neo4j ingestion script and local fallback.
- FastAPI, WebSocket, mod-state stub, and demo UI.
- Data validation and evaluation harness.

Still to expand:

- Full-game crawler and normalization.
- Larger strategy knowledge base.
- Real ModTheSpire/BaseMod or CommunicationMod bridge.
- Deeper combat search and potion planning.
