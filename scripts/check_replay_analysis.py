from pathlib import Path
import sys
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.replay_mod_payloads import load_jsonl, replay_record

SAMPLE = ROOT / "data" / "mod_payload_replay_sample.jsonl"


def main() -> None:
    records = load_jsonl(SAMPLE)
    errors: List[str] = []
    if not records:
        raise SystemExit(f"{SAMPLE} should contain at least one replay record.")
    report = replay_record(records[0])
    analysis: Dict[str, Any] = report.get("analysis", {})
    required = [
        "candidate_options",
        "candidate_count",
        "has_skip_option",
        "top",
        "runner_up",
        "score_gap",
        "score_spread",
        "skip_rank",
        "top_reasons",
        "option_summaries",
        "quality_flags",
    ]
    for key in required:
        if key not in analysis:
            errors.append(f"Replay analysis missing {key}.")
    if analysis.get("candidate_count") != 3:
        errors.append(f"Expected 3 replay candidates, got {analysis.get('candidate_count')}.")
    if analysis.get("top", {}).get("option_id") != "catalyst":
        errors.append(f"Expected Catalyst as replay top option, got {analysis.get('top')}.")
    if not analysis.get("top_reasons"):
        errors.append("Replay analysis should expose top_reasons for tuning.")
    if len(analysis.get("option_summaries", [])) < 3:
        errors.append("Replay analysis should summarize each candidate option.")
    if errors:
        raise SystemExit("\n".join(errors))
    print("Replay analysis checks passed: candidate summaries, score gap, skip rank, and tuning reasons.")


if __name__ == "__main__":
    main()
