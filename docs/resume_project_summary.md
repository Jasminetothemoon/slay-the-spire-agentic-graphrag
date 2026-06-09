# Resume Project Summary

## Project Title

Mod-first Multi-Agent Decision Harness for Slay the Spire

## One-Line Pitch

Built a real-time in-game AI decision assistant that combines a Java Mod bridge, LangGraph multi-agent workflow, pluggable Decision Skills, GraphRAG retrieval, deterministic scoring, and replay/evaluation harnesses for complex strategy-game decisions.

## Resume Bullets

- Built a ModTheSpire/BaseMod in-game assistant that reads live Slay the Spire run state, calls a local FastAPI recommendation service, and renders candidate score badges, hover explanations, target archetype controls, and Chinese/English UI directly inside the game.
- Designed a LangGraph workflow with State, Scene Router, Retrieval, Risk, Skill Scoring, Critic, and Explainer agents; exposed structured `agent_trace`, `selected_skill`, critic warnings, and decision validity for debugging and replay.
- Implemented a pluggable Decision Skill system covering card picks, relic picks, shops, pathing, combat turns, and rest-site decisions, with deterministic scoring instead of external LLM calls in the real-time path.
- Built a provenance-tracked knowledge graph from public game data with 666 entities and 1442 relationships; supported Neo4j GraphRAG retrieval with local JSON fallback for reliable offline demos.
- Added replay/eval/ablation/latency harnesses over 54 fixed scenarios and real Mod JSONL payloads, reporting Top-1/Top-3 accuracy, P95 latency, no-recommendation rate, critic warnings, and tuning flags such as low score separation.

## Interview Talking Points

### Why This Is More Than a Game Bot

The project is framed as a complex decision-support system under real-time constraints. Slay the Spire provides rich state, partial future risk, archetype-dependent choices, and high variance, which makes it a useful proxy for AI application problems such as retrieval, workflow orchestration, evaluation, and explainable recommendations.

### Multi-Agent Design

The agents are not separate chatbots. They are deterministic workflow roles:

- StateAgent validates and normalizes state.
- SceneRouterAgent selects a Decision Skill.
- RetrievalAgent fetches graph and strategy evidence.
- RiskAgent detects deck/run risks.
- SkillScoringAgent scores candidates.
- CriticAgent checks illegal or stale recommendations.
- ExplainerAgent returns structured reasons and UI-ready explanations.

This is interview-friendly because each agent has a concrete responsibility, observable trace, and failure mode.

### Skill System

Decision Skills make the system extensible. A card reward, shop screen, Boss relic choice, and combat turn do not share the same scoring logic, but they share the same interface. This lets new skills be added without rewriting the agent workflow.

### Harness Value

The harness is the strongest engineering signal:

- Replay Harness reproduces real Mod payloads.
- Eval Harness measures fixed labeled cases.
- Ablation Harness shows the effect of graph, strategy, risk, and critic components.
- Latency Harness tracks P50/P95/P99.
- Replay analysis flags low top separation, skip ranking, captured-vs-replay drift, and critic warnings.

This turns subjective "the recommendation feels wrong" feedback into reproducible debugging data.

## Current Metrics

| Metric | Value |
| --- | ---: |
| Graph entities | 666 |
| Graph relationships | 1442 |
| Fixed eval cases | 54 |
| Tracked archetypes | 20 |
| Chinese localization coverage | 91.5% |
| Missing relationship provenance | 0 |
| Local P95 latency | about 2-3 ms |

## Honest Limitations

- Evaluation is still curated and should expand to 200+ human-labeled real-game cases.
- Event decisions are not implemented yet.
- Map capture is conservative in the Java Mod because earlier live map state caused instability.
- Combat recommendations are shallow and should eventually use deeper search.
- Strategy knowledge is seeded and traceable, but not yet a complete expert-policy model.

## Stronger Future Version

The next high-value version should add:

- More real captured payloads from full runs.
- Human labels for high-level card, relic, shop, and Boss relic choices.
- A tuning report showing recommendation changes before and after calibration.
- More community-derived archetype rules with source URLs and confidence scores.
- A short demo GIF/video showing Mod launch, F11 archetype selection, candidate badges, and replay report.
