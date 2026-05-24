import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


COLLECTIONS = [
    "classes",
    "mechanics",
    "cards",
    "relics",
    "potions",
    "enemies",
    "archetypes",
    "shop_actions",
    "path_nodes",
]

PROVENANCE_FIELDS = ["source", "source_url", "confidence"]
VERSION_FIELDS = ["patch_version", "version"]


def present(item: Dict[str, Any], field: str) -> bool:
    return item.get(field) not in (None, "", [], {})


def pct(part: int, total: int) -> float:
    if total == 0:
        return 100.0
    return round(part * 100.0 / total, 2)


def sample_missing(items: List[Dict[str, Any]], field: str, limit: int) -> List[str]:
    missing = []
    for item in items:
        if not present(item, field):
            missing.append(item.get("id") or item.get("name") or "<unknown>")
        if len(missing) >= limit:
            break
    return missing


def source_counts(items: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = Counter(str(item.get("source") or "missing") for item in items)
    return dict(sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])))


def confidence_stats(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    values = [float(item["confidence"]) for item in items if isinstance(item.get("confidence"), (int, float))]
    if not values:
        return {"count": 0, "min": None, "max": None, "avg": None}
    return {
        "count": len(values),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
        "avg": round(sum(values) / len(values), 3),
    }


def relationship_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_relationships = 0
    missing_evidence = 0
    type_counts: Counter[str] = Counter()
    for item in items:
        for rel in item.get("relationships", []):
            total_relationships += 1
            type_counts[str(rel.get("type") or "missing")] += 1
            if not any(present(rel, field) for field in ("source", "source_url", "evidence", "confidence")):
                missing_evidence += 1
    return {
        "total": total_relationships,
        "missing_evidence": missing_evidence,
        "missing_evidence_pct": pct(missing_evidence, total_relationships),
        "types": dict(sorted(type_counts.items())),
    }


def collection_report(name: str, items: List[Dict[str, Any]], sample_limit: int) -> Dict[str, Any]:
    count = len(items)
    fields = {}
    for field in PROVENANCE_FIELDS + VERSION_FIELDS:
        present_count = sum(1 for item in items if present(item, field))
        fields[field] = {
            "present": present_count,
            "missing": count - present_count,
            "coverage_pct": pct(present_count, count),
            "missing_examples": sample_missing(items, field, sample_limit),
        }
    return {
        "count": count,
        "source_counts": source_counts(items),
        "confidence": confidence_stats(items),
        "fields": fields,
        "relationships": relationship_summary(items),
    }


def build_report(data: Dict[str, Any], sample_limit: int) -> Dict[str, Any]:
    return {
        "metadata": data.get("metadata", {}),
        "collections": {
            collection: collection_report(collection, data.get(collection, []), sample_limit)
            for collection in COLLECTIONS
        },
    }


def print_human(report: Dict[str, Any]) -> None:
    print("Data Provenance Report")
    print("======================")
    metadata = report.get("metadata", {})
    if metadata:
        print(f"Dataset: {metadata.get('name', 'unknown')}")
        print(f"Patch: {metadata.get('patch_version', 'unknown')}")
    print()
    for collection, info in report["collections"].items():
        print(f"{collection}: {info['count']}")
        for field, field_info in info["fields"].items():
            print(
                f"  {field}: {field_info['coverage_pct']}% "
                f"({field_info['present']}/{info['count']})"
            )
            if field_info["missing_examples"]:
                print(f"    missing examples: {', '.join(field_info['missing_examples'])}")
        relationships = info["relationships"]
        if relationships["total"]:
            print(
                f"  relationships: {relationships['total']}, "
                f"missing evidence: {relationships['missing_evidence_pct']}%"
            )
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Report source/provenance coverage for a knowledge dataset.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON instead of a human report.")
    parser.add_argument("--sample-limit", type=int, default=5)
    args = parser.parse_args()

    with open(Path(args.data), "r", encoding="utf-8") as f:
        data = json.load(f)

    report = build_report(data, sample_limit=args.sample_limit)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)


if __name__ == "__main__":
    main()
