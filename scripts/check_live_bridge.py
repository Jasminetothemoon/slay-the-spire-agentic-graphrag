import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List
from urllib import request

import websockets


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENARIOS = ROOT / "data" / "bridge_scenarios.json"
DEFAULT_DATA = ROOT / "data" / "public_full_data.json"


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def post_json(base_url: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_health(base_url: str, timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with request.urlopen(f"{base_url}/health", timeout=2) as response:
                if response.status == 200:
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(0.2)
    raise RuntimeError(f"API did not become healthy at {base_url}: {last_error}")


def start_api(port: int, data_path: Path) -> subprocess.Popen[Any]:
    env = os.environ.copy()
    env["STS_KB_PATH"] = str(data_path)
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def scenario_payload(scenario: Dict[str, Any]) -> Dict[str, Any]:
    decision = scenario["decision"]
    return {
        "state": scenario["state"],
        "query_type": decision["query_type"],
        "options": decision["options"],
        "user_query": decision.get("user_query", ""),
    }


async def collect_bridge_events(base_url: str, scenario: Dict[str, Any]) -> Dict[str, Any]:
    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws"
    events: List[Dict[str, Any]] = []
    async with websockets.connect(ws_url) as websocket:
        events.append(json.loads(await asyncio.wait_for(websocket.recv(), timeout=5)))
        response = await asyncio.to_thread(post_json, base_url, "/mod/recommend", scenario_payload(scenario))
        while len(events) < 3:
            events.append(json.loads(await asyncio.wait_for(websocket.recv(), timeout=5)))
        return {"http_response": response, "events": events}


def validate_events(result: Dict[str, Any], scenario: Dict[str, Any]) -> List[str]:
    errors = []
    events = result["events"]
    event_types = [event.get("type") for event in events]
    if "connected" not in event_types:
        errors.append("WebSocket did not emit connected event.")
    if "state_updated" not in event_types:
        errors.append("WebSocket did not emit state_updated event.")
    if "recommendation" not in event_types:
        errors.append("WebSocket did not emit recommendation event.")
    recommendation = result["http_response"].get("recommendation", {})
    scores = recommendation.get("option_scores", [])
    if not scores:
        errors.append("HTTP /mod/recommend response did not include option_scores.")
    elif scores[0].get("option_id") != recommendation.get("recommendation"):
        errors.append("Top score does not match recommendation id.")
    expected_options = set(scenario["decision"].get("options", []))
    returned_names = {score.get("name") for score in scores}
    if expected_options and not expected_options.intersection(returned_names):
        errors.append("Recommendation scores do not contain the submitted option names.")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local API and verify bridge HTTP requests broadcast overlay WebSocket events.")
    parser.add_argument("--scenario-index", type=int, default=0)
    parser.add_argument("--all-scenarios", action="store_true", help="Verify every scenario in the scenario file.")
    parser.add_argument("--scenarios", default=str(DEFAULT_SCENARIOS))
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--port", type=int, default=0, help="Port to use. Defaults to a free ephemeral port.")
    args = parser.parse_args()

    port = args.port or free_port()
    base_url = f"http://127.0.0.1:{port}"
    scenarios = load_json(Path(args.scenarios))
    process = start_api(port, Path(args.data))
    try:
        wait_for_health(base_url, timeout_s=20)
        selected = scenarios if args.all_scenarios else [scenarios[args.scenario_index]]
        reports = []
        all_errors = []
        for scenario in selected:
            result = asyncio.run(collect_bridge_events(base_url, scenario))
            errors = validate_events(result, scenario)
            if errors:
                all_errors.extend(f"{scenario['id']}: {error}" for error in errors)
                continue
            reports.append(
                {
                    "scenario_id": scenario["id"],
                    "event_types": [event.get("type") for event in result["events"]],
                    "recommendation": result["http_response"]["recommendation"]["recommendation"],
                    "top_option": result["http_response"]["recommendation"]["option_scores"][0]["name"],
                }
            )
        if all_errors:
            raise SystemExit("\n".join(all_errors))
        print(
            json.dumps(
                {
                    "status": "passed",
                    "base_url": base_url,
                    "scenarios": reports,
                },
                indent=2,
            )
        )
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    main()
