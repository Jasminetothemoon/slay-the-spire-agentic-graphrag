import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sts_engine.knowledge_base import load_knowledge_base

DEFAULT_DATA = ROOT / "data" / "public_full_data.json"
DEFAULT_FIXTURES = ROOT / "data" / "graph_query_fixtures.json"


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_fixture(kb: Any, fixture: Dict[str, Any]) -> List[str]:
    state = fixture["state"]
    evidence = kb.find_synergies(
        list(state.get("deck", [])) + list(state.get("relics", [])) + list(state.get("potions", [])),
        state.get("options", []),
    )
    option_ids = {item["option_id"] for item in evidence}
    mechanics = {item["mechanic"] for item in evidence}
    errors = []
    required_fields = {
        "owned_source",
        "owned_source_url",
        "owned_confidence",
        "option_source",
        "option_source_url",
        "option_confidence",
    }
    for option_id in fixture["expected"].get("option_ids", []):
        if option_id not in option_ids:
            errors.append(f"{fixture['id']}: missing option evidence for {option_id}")
    for mechanic in fixture["expected"].get("mechanics", []):
        if mechanic not in mechanics:
            errors.append(f"{fixture['id']}: missing mechanic evidence for {mechanic}")
    for item in evidence:
        missing_fields = [field for field in required_fields if item.get(field) in (None, "")]
        if missing_fields:
            errors.append(f"{fixture['id']}: evidence missing provenance fields {missing_fields}")
        for field in ("owned_id", "option_id"):
            if item.get(field) in {"derived_relationship", "public_dataset", "manual_strategy"}:
                errors.append(f"{fixture['id']}: {field} contains provenance marker {item[field]}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Check graph retrieval fixtures against the local JSON fallback graph.")
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--fixtures", default=str(DEFAULT_FIXTURES))
    args = parser.parse_args()

    os.environ["STS_KB_PATH"] = str(Path(args.data))
    load_knowledge_base.cache_clear()
    kb = load_knowledge_base(str(Path(args.data)))
    fixtures = load_json(Path(args.fixtures))
    errors = []
    for fixture in fixtures:
        errors.extend(check_fixture(kb, fixture))
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Graph fixture checks passed: {len(fixtures)}")


if __name__ == "__main__":
    main()
