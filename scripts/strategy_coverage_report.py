import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COVERAGE = ROOT / "data" / "strategy" / "archetype_coverage.json"
DEFAULT_ARCHETYPES = ROOT / "data" / "strategy" / "archetypes.json"
DEFAULT_EVAL = ROOT / "data" / "public_eval_cases.json"


def load_json(path: Path) -> Dict[str, Any] | List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description="Report archetype strategy coverage and evaluation support.")
    parser.add_argument("--coverage", default=str(DEFAULT_COVERAGE))
    parser.add_argument("--archetypes", default=str(DEFAULT_ARCHETYPES))
    parser.add_argument("--eval", default=str(DEFAULT_EVAL))
    args = parser.parse_args()

    coverage = load_json(Path(args.coverage))
    archetypes = load_json(Path(args.archetypes))
    eval_cases = load_json(Path(args.eval))

    implemented = {item["id"] for item in archetypes.get("archetypes", [])}
    eval_text = json.dumps(eval_cases)
    rows = []
    status_counts = Counter()
    implemented_count = 0
    eval_supported_count = 0
    total = 0

    for class_name, items in coverage.get("classes", {}).items():
        for item in items:
            total += 1
            status = item["status"]
            status_counts[status] += 1
            has_rules = item["id"] in implemented
            has_eval = item["id"] in eval_text or any(part in eval_text for part in item["id"].split("_")[1:])
            implemented_count += int(has_rules)
            eval_supported_count += int(has_eval)
            rows.append(
                {
                    "class": class_name,
                    "id": item["id"],
                    "name": item["name"],
                    "status": status,
                    "priority": item["priority"],
                    "has_rules": has_rules,
                    "has_eval_signal": has_eval,
                }
            )

    report = {
        "total_tracked_archetypes": total,
        "implemented_rule_coverage": round(implemented_count / total, 3) if total else 0,
        "eval_signal_coverage": round(eval_supported_count / total, 3) if total else 0,
        "status_counts": dict(status_counts),
        "rows": rows,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
