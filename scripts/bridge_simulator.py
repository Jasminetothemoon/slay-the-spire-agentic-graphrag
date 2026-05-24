import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_SCENARIOS = ROOT / "data" / "bridge_scenarios.json"


def load_scenarios(path: Path) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_offline(scenarios: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from sts_engine.agent import build_graph

    engine = build_graph()
    results = []
    for scenario in scenarios:
        state = dict(scenario["state"])
        decision = scenario["decision"]
        state.update(
            {
                "query_type": decision["query_type"],
                "options": decision["options"],
                "user_query": decision.get("user_query", ""),
            }
        )
        final_state = engine.invoke(state)
        results.append(
            {
                "scenario_id": scenario["id"],
                "recommendation": final_state.get("recommendation"),
                "reasoning": final_state.get("reasoning"),
                "top_scores": final_state.get("option_scores", [])[:3],
            }
        )
    return results


def post_json(base_url: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    import requests

    response = requests.post(f"{base_url.rstrip('/')}{path}", json=payload, timeout=15)
    response.raise_for_status()
    return response.json()


def run_http(base_url: str, scenarios: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    for scenario in scenarios:
        state_response = post_json(base_url, "/mod/state", scenario["state"])
        run_id = state_response["run_id"]
        decision = dict(scenario["decision"])
        decision["run_id"] = run_id
        recommendation = post_json(base_url, "/get_recommendation", decision)
        results.append(
            {
                "scenario_id": scenario["id"],
                "run_id": run_id,
                "recommendation": recommendation.get("recommendation"),
                "reasoning": recommendation.get("reasoning"),
                "top_scores": recommendation.get("option_scores", [])[:3],
            }
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate a game-state bridge posting snapshots to the recommender.")
    parser.add_argument("--scenarios", default=str(DEFAULT_SCENARIOS))
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--mode", choices=["offline", "http"], default="offline")
    parser.add_argument("--data", default=None, help="Optional STS_KB_PATH override for offline mode.")
    args = parser.parse_args()

    if args.data:
        os.environ["STS_KB_PATH"] = args.data

    scenarios = load_scenarios(Path(args.scenarios))
    if args.mode == "http":
        results = run_http(args.base_url, scenarios)
    else:
        results = run_offline(scenarios)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
