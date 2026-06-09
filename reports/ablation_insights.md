# Ablation and Baseline Insights

This report is generated from the fixed eval set. It compares simple deterministic baselines, the full Multi-Agent Decision Harness, and module-level ablations.

- Eval file: `data\public_eval_cases.json`
- Cases: 54
- Full system Top-1 / Top-3: 1.0 / 1.0
- Full system P95 latency: 2.12 ms

## Baseline Comparison

| Variant | Cases | Top-1 | Top-3 | P95 ms | No Recommendation | Critic Warning | Delta vs Full |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| input_order | 54 | 0.685 | 0.759 | 0.0 | 0.167 | 0.0 | Top-1 -0.315, Top-3 -0.241 |
| base_value | 54 | 0.593 | 0.759 | 0.0 | 0.167 | 0.0 | Top-1 -0.407, Top-3 -0.241 |
| full_multi_agent | 54 | 1.0 | 1.0 | 2.12 | 0.0 | 0.0 | reference |

## Module Ablation

| Variant | Cases | Top-1 | Top-3 | P95 ms | No Recommendation | Critic Warning | Delta vs Full |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| full | 54 | 1.0 | 1.0 | 1.85 | 0.0 | 0.0 | Top-1 0.0, Top-3 0.0, P95 -0.27 ms |
| no_graph | 54 | 0.981 | 1.0 | 1.85 | 0.0 | 0.0 | Top-1 -0.019, Top-3 0.0, P95 -0.27 ms |
| no_strategy | 54 | 0.87 | 1.0 | 1.83 | 0.0 | 0.0 | Top-1 -0.13, Top-3 0.0, P95 -0.29 ms |
| no_risk | 54 | 0.981 | 1.0 | 1.78 | 0.0 | 0.0 | Top-1 -0.019, Top-3 0.0, P95 -0.34 ms |
| no_critic | 54 | 1.0 | 1.0 | 1.86 | 0.0 | 0.0 | Top-1 0.0, Top-3 0.0, P95 -0.26 ms |

## Full System By Query Type

| Query Type | Cases | Top-1 | Top-3 |
| --- | ---: | ---: | ---: |
| card_pick | 22 | 1.0 | 1.0 |
| combat | 5 | 1.0 | 1.0 |
| pathing | 11 | 1.0 | 1.0 |
| relic_pick | 8 | 1.0 | 1.0 |
| shop | 8 | 1.0 | 1.0 |

## Interview Takeaways

- `input_order` measures how often the eval fixture order accidentally puts the best option first.
- `base_value` measures a naive tier/value strategy that ignores deck state, target archetype, graph evidence, risk, price, and legality.
- `full_multi_agent` is the production path: StateAgent -> SceneRouterAgent -> RetrievalAgent -> RiskAgent -> SkillScoringAgent -> CriticAgent -> ExplainerAgent.
- Module ablations are most useful after adding more real, noisy payloads; on a curated eval set they mainly verify that switches stay stable and measurable.
- The key engineering value is not a single score, but a repeatable harness that can compare recommendation policies as the dataset grows.
