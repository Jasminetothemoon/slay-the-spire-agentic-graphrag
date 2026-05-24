import argparse
import json
from pathlib import Path
from typing import Any, Dict


DEFAULT_TARGETS = Path("data") / "coverage_targets.json"


def pct(current: int, target: int) -> float:
    if target <= 0:
        return 100.0
    return round(min(current / target, 1.0) * 100.0, 2)


def load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def current_count(data: Dict[str, Any], collection: str) -> int:
    if collection == "events":
        return len(data.get("events", []))
    return len(data.get(collection, []))


def build_report(data: Dict[str, Any], targets: Dict[str, Any]) -> Dict[str, Any]:
    collections = {}
    for collection, target in targets.items():
        target_count = int(target.get("target_count", 0))
        current = current_count(data, collection)
        collections[collection] = {
            "current": current,
            "target": target_count,
            "gap": max(target_count - current, 0),
            "coverage_pct": pct(current, target_count),
            "required_for_mod_mvp": bool(target.get("required_for_mod_mvp", False)),
            "notes": target.get("notes", ""),
        }
    required = [info for info in collections.values() if info["required_for_mod_mvp"]]
    required_target = sum(info["target"] for info in required)
    required_current = sum(min(info["current"], info["target"]) for info in required)
    return {
        "metadata": data.get("metadata", {}),
        "required_mod_mvp_coverage_pct": pct(required_current, required_target),
        "collections": collections,
    }


def print_human(report: Dict[str, Any]) -> None:
    print("Data Coverage Report")
    print("====================")
    print(f"Required Mod MVP coverage: {report['required_mod_mvp_coverage_pct']}%")
    print()
    for name, info in report["collections"].items():
        required = "required" if info["required_for_mod_mvp"] else "optional"
        print(
            f"{name}: {info['current']}/{info['target']} "
            f"({info['coverage_pct']}%, gap {info['gap']}, {required})"
        )
        if info["notes"]:
            print(f"  {info['notes']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare current dataset counts against practical Mod MVP coverage targets.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--targets", default=str(DEFAULT_TARGETS))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fail-under", type=float, default=None, help="Exit with status 1 if required Mod MVP coverage is below this percentage.")
    args = parser.parse_args()

    data = load_json(Path(args.data))
    targets = load_json(Path(args.targets))
    report = build_report(data, targets)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)
    if args.fail_under is not None and report["required_mod_mvp_coverage_pct"] < args.fail_under:
        raise SystemExit(
            f"Required Mod MVP coverage {report['required_mod_mvp_coverage_pct']}% is below threshold {args.fail_under}%."
        )


if __name__ == "__main__":
    main()
