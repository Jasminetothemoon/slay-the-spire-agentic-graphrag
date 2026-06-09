# Agent Trace Audit

This report expands representative recommendation cases into an interview-readable Multi-Agent trace.

- Eval file: `data\public_eval_cases.json`
- Audited cases: 6
- Valid decisions: 6/6
- Complete traces: 6/6
- Cases with critic warnings: 0/6

## Required Agent Contract

- StateAgent
- SceneRouterAgent
- RetrievalAgent
- RiskAgent
- SkillScoringAgent
- CriticAgent
- ExplainerAgent

## Case: public_silent_poison_take_catalyst

- Query type: `card_pick`
- Scene type: `card_reward`
- Selected skill: `card_pick_skill`
- Decision valid: True
- Latency: 1.88 ms
- Expected top: `catalyst`
- Ranked Top-3: catalyst, dagger_spray, backflip
- Critic warnings: none
- Missing agents: none

### Top Recommendation

- Option: `catalyst` / Catalyst
- Score: 93.88, confidence 0.88
- Evidence count: 5
- Reasons:
  - Graph synergy with current run: Poison.
  - Archetype fit: Silent Poison.
  - Poison payoff is premium once the deck already applies Poison.
  - Matches the current character card pool.

### Runner-Up Tradeoff

- Option: `dagger_spray` / Dagger Spray
- Score: 81.4
- Why not: No major drawback recorded.

### Agent Trace

- **StateAgent**: scene_type=card_reward; errors=0
- **SceneRouterAgent**: selected_skill=card_pick_skill; options_count=3
- **RetrievalAgent**: context_count=8
- **RiskAgent**: risks=
- **SkillScoringAgent**: scores=3; selected_skill=card_pick_skill
- **CriticAgent**: warnings=0; decision_valid=True
- **ExplainerAgent**: recommendation=catalyst

## Case: public_shop_remove_card

- Query type: `shop`
- Scene type: `shop`
- Selected skill: `shop_skill`
- Decision valid: True
- Latency: 1.22 ms
- Expected top: `remove_card`
- Ranked Top-3: remove_card, buy_potion, skip_shop
- Critic warnings: none
- Missing agents: none

### Top Recommendation

- Option: `remove_card` / Remove a Card
- Score: 78.0, confidence 0.51
- Evidence count: 0
- Reasons:
  - Card removal improves deck consistency.

### Runner-Up Tradeoff

- Option: `buy_potion` / Buy Potion
- Score: 48.0
- Why not: No major drawback recorded.

### Agent Trace

- **StateAgent**: scene_type=shop; errors=0
- **SceneRouterAgent**: selected_skill=shop_skill; options_count=3
- **RetrievalAgent**: context_count=0
- **RiskAgent**: risks=slow_scaling, shop_ready
- **SkillScoringAgent**: scores=3; selected_skill=shop_skill
- **CriticAgent**: warnings=0; decision_valid=True
- **ExplainerAgent**: recommendation=remove_card

## Case: public_relic_silent_shiv_take_shuriken

- Query type: `relic_pick`
- Scene type: `relic_reward`
- Selected skill: `relic_pick_skill`
- Decision valid: True
- Latency: 1.25 ms
- Expected top: `shuriken`
- Ranked Top-3: shuriken, blue_candle, tiny_chest
- Critic warnings: none
- Missing agents: none

### Top Recommendation

- Option: `shuriken` / Shuriken
- Score: 80.92, confidence 0.8
- Evidence count: 4
- Reasons:
  - Graph synergy with current run: Frontload Damage, Shiv.
  - Archetype fit: Silent Shiv.
  - Shuriken covers slow_scaling for Silent Shiv.

### Runner-Up Tradeoff

- Option: `blue_candle` / Blue Candle
- Score: 68.0
- Why not: No major drawback recorded.

### Agent Trace

- **StateAgent**: scene_type=relic_reward; errors=0
- **SceneRouterAgent**: selected_skill=relic_pick_skill; options_count=3
- **RetrievalAgent**: context_count=3
- **RiskAgent**: risks=no_aoe, slow_scaling
- **SkillScoringAgent**: scores=3; selected_skill=relic_pick_skill
- **CriticAgent**: warnings=0; decision_valid=True
- **ExplainerAgent**: recommendation=shuriken

## Case: public_combat_silent_block_potion

- Query type: `combat`
- Scene type: `combat`
- Selected skill: `combat_skill`
- Decision valid: True
- Latency: 2.64 ms
- Expected top: `use_block_potion`
- Ranked Top-3: use_block_potion, play_neutralize_then_survivor_then_strike_silent_then_defend_silent, play_neutralize_then_survivor_then_defend_silent_then_strike_silent
- Critic warnings: none
- Missing agents: none

### Top Recommendation

- Option: `use_block_potion` / Use Block Potion
- Score: 82.0, confidence 0.62
- Evidence count: 1
- Reasons:
  - Incoming damage is high enough that a defensive potion can preserve HP.
- Risks:
  - Potion use spends a limited resource.

### Runner-Up Tradeoff

- Option: `play_neutralize_then_survivor_then_strike_silent_then_defend_silent` / Neutralize -> Survivor -> Strike -> Defend
- Score: 69.42
- Why not: No major drawback recorded.

### Agent Trace

- **StateAgent**: scene_type=combat; errors=0
- **SceneRouterAgent**: selected_skill=combat_skill; options_count=4
- **RetrievalAgent**: context_count=0
- **RiskAgent**: risks=no_aoe
- **SkillScoringAgent**: scores=5; selected_skill=combat_skill
- **CriticAgent**: warnings=0; decision_valid=True
- **ExplainerAgent**: recommendation=use_block_potion

## Case: public_pathing_low_hp_take_rest_route

- Query type: `pathing`
- Scene type: `map`
- Selected skill: `pathing_skill`
- Decision valid: True
- Latency: 1.13 ms
- Expected top: `path_monster_rest_treasure`
- Ranked Top-3: path_monster_rest_treasure, rest, elite
- Critic warnings: none
- Missing agents: none

### Top Recommendation

- Option: `path_monster_rest_treasure` / Monster > Rest > Treasure
- Score: 78.0, confidence 0.59
- Evidence count: 1
- Reasons:
  - Rest site gives a recovery exit before the route becomes dangerous.

### Runner-Up Tradeoff

- Option: `rest` / Rest Site
- Score: 72.0
- Why not: No major drawback recorded.

### Agent Trace

- **StateAgent**: scene_type=map; errors=0
- **SceneRouterAgent**: selected_skill=pathing_skill; options_count=4
- **RetrievalAgent**: context_count=0
- **RiskAgent**: risks=no_aoe, low_hp
- **SkillScoringAgent**: scores=4; selected_skill=pathing_skill
- **CriticAgent**: warnings=0; decision_valid=True
- **ExplainerAgent**: recommendation=path_monster_rest_treasure

## Case: public_silent_missing_aoe_take_dagger_spray

- Query type: `card_pick`
- Scene type: `card_reward`
- Selected skill: `card_pick_skill`
- Decision valid: True
- Latency: 1.11 ms
- Expected top: `dagger_spray`
- Ranked Top-3: dagger_spray, catalyst, deadly_poison
- Critic warnings: none
- Missing agents: none

### Top Recommendation

- Option: `dagger_spray` / Dagger Spray
- Score: 87.7, confidence 0.63
- Evidence count: 1
- Reasons:
  - Graph synergy with current run: Frontload Damage.
  - Fixes an AoE weakness before multi-enemy fights.
  - Matches the current character card pool.

### Runner-Up Tradeoff

- Option: `catalyst` / Catalyst
- Score: 66.0
- Why not: No major drawback recorded.

### Agent Trace

- **StateAgent**: scene_type=card_reward; errors=0
- **SceneRouterAgent**: selected_skill=card_pick_skill; options_count=3
- **RetrievalAgent**: context_count=1
- **RiskAgent**: risks=no_aoe
- **SkillScoringAgent**: scores=3; selected_skill=card_pick_skill
- **CriticAgent**: warnings=0; decision_valid=True
- **ExplainerAgent**: recommendation=dagger_spray

## Interview Takeaways

- The workflow is observable: every recommendation records routing, retrieval, risk, scoring, critic, and explanation steps.
- CriticAgent is a guardrail for stale scenes, empty options, and illegal recommendations; it reports warnings without crashing the Mod.
- This trace format can be attached to replay payloads, turning subjective recommendation complaints into inspectable cases.
