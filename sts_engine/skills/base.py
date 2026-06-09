from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Set


class DecisionSkill(ABC):
    id: str
    query_types: Set[str]

    def supports(self, state: Dict[str, Any]) -> bool:
        return state.get("query_type") in self.query_types

    def build_options(self, state: Dict[str, Any]) -> List[Any]:
        return list(state.get("options") or [])

    def retrieve_context(self, state: Dict[str, Any], options: List[Any]) -> List[Dict[str, Any]]:
        return []

    @abstractmethod
    def score(self, state: Dict[str, Any], options: List[Any], context: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def explain(self, state: Dict[str, Any], scores: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "skill_id": self.id,
            "summary": f"{self.id} scored {len(scores)} option(s).",
        }

    def validate(self, state: Dict[str, Any], scores: List[Dict[str, Any]]) -> List[str]:
        warnings = []
        if not scores:
            warnings.append(f"{self.id} returned no option scores.")
        return warnings
