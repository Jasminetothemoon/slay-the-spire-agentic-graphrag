import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List

from bridge_simulator import DEFAULT_SCENARIOS, load_scenarios, post_json


def request_recommendation(base_url: str, scenario: Dict[str, Any], legacy_two_step: bool) -> Dict[str, Any]:
    if legacy_two_step:
        state_response = post_json(base_url, "/mod/state", scenario["state"])
        decision = dict(scenario["decision"])
        decision["run_id"] = state_response["run_id"]
        recommendation = post_json(base_url, "/get_recommendation", decision)
        return {"run_id": state_response["run_id"], "recommendation": recommendation}

    decision = scenario["decision"]
    response = post_json(
        base_url,
        "/mod/recommend",
        {
            "state": scenario["state"],
            "query_type": decision["query_type"],
            "options": decision["options"],
            "user_query": decision.get("user_query", ""),
        },
    )
    return {"run_id": response["run_id"], "recommendation": response["recommendation"]}


def play_scenarios(base_url: str, scenarios: List[Dict[str, Any]], delay: float, loops: int, legacy_two_step: bool) -> List[Dict[str, Any]]:
    history: List[Dict[str, Any]] = []
    for loop_index in range(loops):
        for scenario in scenarios:
            print(f"[bridge-demo] posting state: {scenario['id']} - {scenario.get('description', '')}")
            result = request_recommendation(base_url, scenario, legacy_two_step=legacy_two_step)
            run_id = result["run_id"]
            recommendation = result["recommendation"]

            top_scores = recommendation.get("option_scores", [])[:3]
            top_name = top_scores[0]["name"] if top_scores else recommendation.get("recommendation", "unknown")
            print(f"[bridge-demo] recommendation for {run_id}: {top_name}")

            history.append(
                {
                    "loop": loop_index + 1,
                    "scenario_id": scenario["id"],
                    "run_id": run_id,
                    "recommendation": recommendation.get("recommendation"),
                    "top_scores": top_scores,
                }
            )
            if delay > 0:
                time.sleep(delay)
    return history


def main() -> None:
    parser = argparse.ArgumentParser(description="Play bridge scenarios over HTTP so the web overlay updates like a live game companion.")
    parser.add_argument("--scenarios", default=str(DEFAULT_SCENARIOS))
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--delay", type=float, default=3.0, help="Seconds to wait between scenarios.")
    parser.add_argument("--loops", type=int, default=1, help="Number of times to replay the scenario list.")
    parser.add_argument("--legacy-two-step", action="store_true", help="Use /mod/state then /get_recommendation instead of /mod/recommend.")
    args = parser.parse_args()

    scenarios = load_scenarios(Path(args.scenarios))
    history = play_scenarios(args.base_url, scenarios, delay=args.delay, loops=args.loops, legacy_two_step=args.legacy_two_step)
    print(json.dumps(history, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
