# Benchmark Report

Generated: 2026-05-29 10:24 UTC

## Executive Summary

- Evaluation cases: **26**
- Top-1 accuracy: **1.0**
- Top-3 accuracy: **1.0**
- Mean latency: **1.2 ms**
- P95 latency: **1.22 ms**
- Graph entities: **666**
- Graph relationships: **1442**
- Community strategy rules: **6 rules from 6 sources**
- Chinese localization coverage: **560/612 (91.5%)**

## Agentic Workflow

The recommendation pipeline is a deterministic LangGraph workflow, not a direct LLM-only answer:

| Step | Responsibility |
| --- | --- |
| validate_state | Check run id, class, query type, and available decision options. |
| retrieve_context | Retrieve graph evidence and shared mechanics for the current state. |
| assess_risk | Detect deck-shape and run-state risks such as missing AoE or low HP. |
| score_options | Score legal options with graph evidence, curated strategy rules, and risk coverage. |
| explain_decision | Return a structured recommendation, latency, confidence, reasons, and risks. |

## Evaluation Metrics

| Query Type | Cases | Top-1 | Top-3 |
| --- | --- | --- | --- |
| card_pick | 22 | 1.0 | 1.0 |
| pathing | 3 | 1.0 | 1.0 |
| shop | 1 | 1.0 | 1.0 |

## Data Scale

| Collection | Count |
| --- | --- |
| classes | 7 |
| mechanics | 35 |
| cards | 367 |
| relics | 146 |
| potions | 42 |
| enemies | 57 |
| shop_actions | 5 |
| path_nodes | 7 |

## Graph Scale

- Relationships with missing provenance: **0**

| Relationship | Count |
| --- | --- |
| APPLIES | 1309 |
| ENHANCES | 81 |
| GOOD_AGAINST | 26 |
| PUNISHES | 24 |
| SCALES_WITH | 2 |

## Localization

- Source: **local_game_jar**
- Localized entity names are presentation-layer fields; internal recommendation logic continues to use stable English ids.
- Chinese display is covered by regression checks in `scripts/check_localization.py`.

## Community Strategy Layer

The scoring layer uses traceable community and wiki heuristics for pathing and archetype advice. These rules are stored in `data/strategy/community_rules.json` and validated by `scripts/check_community_rules.py`.

| Category | Rules |
| --- | --- |
| archetype | 1 |
| pathing | 5 |

| Source Type | Sources |
| --- | --- |
| community_discussion | 3 |
| wiki | 3 |

## Failure Analysis

No failures in the current evaluation set.

## Reproduce

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_report.py --data data\public_full_data.json --eval data\public_eval_cases.json --output reports\benchmark.md
```
