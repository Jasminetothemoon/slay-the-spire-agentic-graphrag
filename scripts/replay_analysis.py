from __future__ import annotations

from typing import Any, Dict, List


def replay_analysis(record: Dict[str, Any], response: Dict[str, Any], latency_ms: float) -> Dict[str, Any]:
    state = record.get("state") or {}
    scores = list(response.get("option_scores") or [])
    options = list(record.get("options") or state.get("options") or [])
    top = scores[0] if scores else {}
    runner_up = scores[1] if len(scores) > 1 else {}
    captured_summary = record.get("response_summary") or {}
    captured_top = str(captured_summary.get("top_recommendation") or "")
    recommendation = str(response.get("recommendation") or "")
    top_option = str(top.get("name") or recommendation)
    score_gap = _score_gap(top, runner_up)
    skip_rank = _skip_rank(scores)
    quality_flags = _quality_flags(
        scores=scores,
        score_gap=score_gap,
        skip_rank=skip_rank,
        captured_top=captured_top,
        replay_top=top_option,
        critic_warnings=list(response.get("critic_warnings") or []),
    )
    return {
        "preferred_archetype": state.get("preferred_archetype", ""),
        "candidate_options": options,
        "candidate_count": len(options),
        "has_skip_option": any(_is_skip(option) for option in options),
        "captured_top": captured_top,
        "top_changed_from_capture": _top_changed(captured_top, top_option),
        "top": _score_summary(top),
        "runner_up": _score_summary(runner_up),
        "score_gap": score_gap,
        "score_spread": _score_spread(scores),
        "skip_rank": skip_rank,
        "skip_score": _skip_score(scores),
        "top_reasons": list(top.get("reasons") or [])[:3],
        "top_risks": list(top.get("risks") or [])[:3],
        "option_summaries": [_score_summary(score) for score in scores[:6]],
        "quality_flags": quality_flags,
        "latency_ms": round(float(latency_ms or 0), 2),
    }


def _score_summary(score: Dict[str, Any]) -> Dict[str, Any]:
    if not score:
        return {}
    return {
        "option_id": score.get("option_id", ""),
        "name": score.get("name", ""),
        "score": score.get("score", 0),
        "grade": score.get("grade", ""),
        "confidence": score.get("confidence", 0),
        "strategy_signal": score.get("strategy_signal", 0),
        "reasons": list(score.get("reasons") or [])[:2],
        "risks": list(score.get("risks") or [])[:2],
        "why_not": score.get("why_not", ""),
    }


def _score_gap(top: Dict[str, Any], runner_up: Dict[str, Any]) -> float:
    if not top or not runner_up:
        return 0.0
    return round(float(top.get("score", 0) or 0) - float(runner_up.get("score", 0) or 0), 2)


def _score_spread(scores: List[Dict[str, Any]]) -> float:
    if len(scores) < 2:
        return 0.0
    values = [float(score.get("score", 0) or 0) for score in scores]
    return round(max(values) - min(values), 2)


def _skip_rank(scores: List[Dict[str, Any]]) -> int | None:
    for index, score in enumerate(scores, start=1):
        if _is_skip(score.get("option_id", "")) or _is_skip(score.get("name", "")):
            return index
    return None


def _skip_score(scores: List[Dict[str, Any]]) -> float | None:
    for score in scores:
        if _is_skip(score.get("option_id", "")) or _is_skip(score.get("name", "")):
            return float(score.get("score", 0) or 0)
    return None


def _is_skip(value: Any) -> bool:
    text = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    return text in {"skip", "skip_card"}


def _top_changed(captured_top: str, replay_top: str) -> bool:
    if not captured_top:
        return False
    return _normalize(captured_top) != _normalize(replay_top)


def _normalize(value: str) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _quality_flags(
    scores: List[Dict[str, Any]],
    score_gap: float,
    skip_rank: int | None,
    captured_top: str,
    replay_top: str,
    critic_warnings: List[str],
) -> List[str]:
    flags: List[str] = []
    if not scores:
        flags.append("no_scores")
    if len(scores) >= 2 and score_gap < 5:
        flags.append("low_top_separation")
    if skip_rank is not None and skip_rank > 3:
        flags.append("skip_available_but_low_rank")
    if _top_changed(captured_top, replay_top):
        flags.append("captured_top_changed")
    if critic_warnings:
        flags.append("critic_warning")
    return flags
