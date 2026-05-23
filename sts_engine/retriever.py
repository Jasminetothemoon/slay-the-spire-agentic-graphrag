import os
from typing import Any, Dict, Iterable, List

from sts_engine.knowledge_base import KnowledgeBase, load_knowledge_base


class GraphRAGRetriever:
    """Graph retriever with Neo4j as the preferred backend and local JSON as fallback."""

    def __init__(self, knowledge_base: KnowledgeBase | None = None):
        self.kb = knowledge_base or load_knowledge_base()
        self.driver = None
        self.backend = "local_json"
        self._connect_neo4j()

    def _connect_neo4j(self) -> None:
        try:
            from neo4j import GraphDatabase

            uri = os.getenv("NEO4J_URI")
            user = os.getenv("NEO4J_USER", "neo4j")
            password = os.getenv("NEO4J_PASSWORD")
            if not uri or not password:
                return
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            with self.driver.session() as session:
                session.run("RETURN 1").consume()
            self.backend = "neo4j"
        except Exception:
            self.driver = None
            self.backend = "local_json"

    def retrieve(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        owned_items = list(state.get("deck", [])) + list(state.get("relics", [])) + list(state.get("potions", []))
        options = state.get("options", [])
        if self.driver:
            try:
                return self._retrieve_neo4j(owned_items, options)
            except Exception:
                self.backend = "local_json"
        return self.kb.find_synergies(owned_items, options)

    def _retrieve_neo4j(self, owned_items: Iterable[str], options: Iterable[str]) -> List[Dict[str, Any]]:
        query = """
        MATCH (owned)-[r1:APPLIES|SCALES_WITH|ENHANCES|COUNTERS|CORE_PIECE_FOR]->(m)
        WHERE owned.id IN $owned_items OR owned.name IN $owned_items
        MATCH (option)-[r2:APPLIES|SCALES_WITH|ENHANCES|COUNTERS|CORE_PIECE_FOR]->(m)
        WHERE option.id IN $options OR option.name IN $options
        RETURN owned.id AS owned_id, owned.name AS owned_name, type(r1) AS owned_relationship,
               option.id AS option_id, option.name AS option_name, type(r2) AS option_relationship,
               m.id AS mechanic, m.name AS mechanic_name,
               coalesce(r1.weight, 0.5) AS owned_weight, coalesce(r2.weight, 0.5) AS option_weight
        LIMIT 100
        """
        evidence = []
        with self.driver.session() as session:
            result = session.run(query, owned_items=list(owned_items), options=list(options))
            for record in result:
                evidence.append(
                    {
                        "type": "shared_mechanic",
                        "owned_id": record["owned_id"],
                        "owned_name": record["owned_name"],
                        "owned_relationship": record["owned_relationship"],
                        "option_id": record["option_id"],
                        "option_name": record["option_name"],
                        "option_relationship": record["option_relationship"],
                        "mechanic": record["mechanic"],
                        "mechanic_name": record["mechanic_name"],
                        "weight": round((float(record["owned_weight"]) + float(record["option_weight"])) / 2, 3),
                    }
                )
        return evidence

    def get_synergy_context(self, current_deck: list, current_relics: list, options: list) -> str:
        evidence = self.kb.find_synergies(current_deck + current_relics, options)
        if not evidence:
            return "No strong graph synergy found."
        return "\n".join(
            f"- {item['option_name']} shares {item['mechanic_name']} with {item['owned_name']} "
            f"({item['owned_relationship']} -> {item['option_relationship']})."
            for item in evidence
        )
