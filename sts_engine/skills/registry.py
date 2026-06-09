from __future__ import annotations

from typing import Any, Dict, Iterable, List

from sts_engine.combat import CombatAdvisor
from sts_engine.retriever import GraphRAGRetriever
from sts_engine.scoring import RecommendationScorer
from sts_engine.skills.base import DecisionSkill
from sts_engine.skills.core import (
    CardPickSkill,
    CombatSkill,
    PathingSkill,
    RelicPickSkill,
    RestSiteSkill,
    ShopSkill,
)


class SkillRegistry:
    def __init__(self, skills: Iterable[DecisionSkill]):
        self.skills: List[DecisionSkill] = list(skills)

    def select(self, state: Dict[str, Any]) -> DecisionSkill:
        for skill in self.skills:
            if skill.supports(state):
                return skill
        return self.skills[0]

    def skill_ids(self) -> List[str]:
        return [skill.id for skill in self.skills]


def build_default_registry(
    scorer: RecommendationScorer,
    retriever: GraphRAGRetriever,
    combat_advisor: CombatAdvisor,
) -> SkillRegistry:
    return SkillRegistry(
        [
            CardPickSkill(scorer, retriever),
            RelicPickSkill(scorer, retriever),
            ShopSkill(scorer, retriever),
            PathingSkill(scorer, retriever),
            CombatSkill(combat_advisor),
            RestSiteSkill(),
        ]
    )
