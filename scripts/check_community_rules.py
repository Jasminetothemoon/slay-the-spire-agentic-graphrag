import json
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES = ROOT / "data" / "strategy" / "community_rules.json"


def load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def expect(errors: List[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def main() -> None:
    data = load_json(DEFAULT_RULES)
    errors: List[str] = []
    source_ids = [source.get("id") for source in data.get("sources", [])]
    rule_ids = [rule.get("id") for rule in data.get("rules", [])]

    expect(errors, data.get("metadata", {}).get("source") == "community_strategy_synthesis", "Missing community metadata source.")
    expect(errors, len(source_ids) >= 5, "Expected at least five strategy sources.")
    expect(errors, len(rule_ids) >= 6, "Expected at least six community rules.")
    expect(errors, len(source_ids) == len(set(source_ids)), "Source ids must be unique.")
    expect(errors, len(rule_ids) == len(set(rule_ids)), "Rule ids must be unique.")

    known_sources = set(source_ids)
    categories = set()
    for source in data.get("sources", []):
        expect(errors, bool(source.get("title")), f"Source {source.get('id')} is missing title.")
        expect(errors, str(source.get("url", "")).startswith("https://"), f"Source {source.get('id')} needs an https URL.")
        expect(errors, source.get("source_type") in {"wiki", "community_discussion"}, f"Source {source.get('id')} has invalid type.")

    for rule in data.get("rules", []):
        rule_id = rule.get("id")
        categories.add(rule.get("category"))
        expect(errors, bool(rule.get("principle")), f"Rule {rule_id} is missing principle.")
        expect(errors, bool(rule.get("applies_to")), f"Rule {rule_id} is missing applies_to.")
        expect(errors, bool(rule.get("positive_signals")), f"Rule {rule_id} is missing positive signals.")
        expect(errors, bool(rule.get("source_ids")), f"Rule {rule_id} is missing source ids.")
        expect(errors, bool(rule.get("implemented_in")), f"Rule {rule_id} is missing implementation pointer.")
        confidence = float(rule.get("confidence", 0))
        expect(errors, 0.5 <= confidence <= 1.0, f"Rule {rule_id} confidence should be between 0.5 and 1.0.")
        for source_id in rule.get("source_ids", []):
            expect(errors, source_id in known_sources, f"Rule {rule_id} references unknown source {source_id}.")

    expect(errors, {"pathing", "archetype"}.issubset(categories), "Rules must cover both pathing and archetype categories.")

    if errors:
        raise SystemExit("\n".join(errors))

    print(
        "Community rules checks passed: "
        f"{len(data.get('rules', []))} rules, {len(data.get('sources', []))} sources, "
        f"categories={sorted(categories)}"
    )


if __name__ == "__main__":
    main()
