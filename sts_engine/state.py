from typing import Any, Dict, List, Literal, Optional, TypedDict


DecisionType = Literal["card_pick", "relic_pick", "shop", "pathing", "combat", "rest_site", "smith"]


class EnemyState(TypedDict, total=False):
    id: str
    name: str
    hp: int
    max_hp: int
    intent: str
    block: int
    buffs: Dict[str, int]
    debuffs: Dict[str, int]


class RouteNode(TypedDict, total=False):
    node_type: str
    act: int
    floor: int
    elite_count_after: int
    rest_count_after: int
    shop_count_after: int
    risk_tags: List[str]


class OptionScore(TypedDict, total=False):
    option_id: str
    name: str
    score: float
    confidence: float
    reasons: List[str]
    risks: List[str]
    evidence: List[Dict[str, Any]]


class RunState(TypedDict, total=False):
    run_id: str
    source: str
    current_screen: str
    game: str
    patch_version: str
    character_class: str
    ascension_level: int
    act: int
    current_floor: int
    current_hp: int
    max_hp: int
    gold: int
    energy: int
    deck: List[str]
    upgraded_cards: List[str]
    relics: List[str]
    potions: List[str]
    combat_state: Dict[str, Any]
    enemies: List[EnemyState]
    hand_cards: List[str]
    draw_pile: List[str]
    discard_pile: List[str]
    map_options: List[RouteNode]
    shop_items: List[Dict[str, Any]]
    boss: Optional[str]
    preferred_archetype: str
    query_type: DecisionType
    scene_type: str
    options: List[Any]
    raw_options: List[Any]
    user_query: str
    skill_options: List[Any]
    selected_skill: str
    agent_trace: List[Dict[str, Any]]
    critic_warnings: List[str]
    decision_valid: bool
    validation_errors: List[str]
    graph_context: List[Dict[str, Any]]
    risk_report: Dict[str, Any]
    option_scores: List[OptionScore]
    recommendation: str
    reasoning: str
    explanation_panel: Dict[str, Any]
    latency_ms: float
    _started_at: float
    _ablation_disable_graph: bool
    _ablation_disable_strategy: bool
    _ablation_disable_risk: bool
    _ablation_disable_critic: bool
