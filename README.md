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

```bash
pip install -r requirements.txt
python scripts/validate_data.py
python scripts/evaluate.py
uvicorn api.main:app --reload
```

Open `http://127.0.0.1:8000` and start a demo run.

## Neo4j Ingestion

Neo4j is optional for local demos. To ingest the graph:

```bash
set NEO4J_URI=bolt://localhost:7687
set NEO4J_USER=neo4j
set NEO4J_PASSWORD=your_password
python scripts/ingest_graph.py --dry-run
python scripts/ingest_graph.py
```

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
