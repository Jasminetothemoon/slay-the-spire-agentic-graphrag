import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from sts_engine.agent import build_graph
from sts_engine.knowledge_base import load_knowledge_base
from sts_engine.localization import localize_response, localize_state


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"

app = FastAPI(
    title="Slay the Spire Agentic GraphRAG API",
    description="Realtime decision assistant with knowledge graph retrieval, structured scoring, and agent workflow.",
    version="2.0.0",
)

if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

engine = build_graph()
kb = load_knowledge_base()
active_runs: Dict[str, Dict[str, Any]] = {}
subscribers: List[WebSocket] = []
mod_diagnostics: Deque[Dict[str, Any]] = deque(maxlen=20)
mod_last_error: Optional[str] = None


def with_localized_state(state: Dict[str, Any]) -> Dict[str, Any]:
    state_with_locale = dict(state)
    state_with_locale["localized"] = {"zh": localize_state(state_with_locale)}
    return state_with_locale


class StartRunRequest(BaseModel):
    character_class: str = Field(default="silent")
    ascension_level: int = Field(default=0, ge=0, le=20)
    max_hp: int = Field(default=70, gt=0)
    source: str = Field(default="manual")


class UpdateStateRequest(BaseModel):
    run_id: str
    source: Optional[str] = None
    act: Optional[int] = None
    current_floor: Optional[int] = None
    current_hp: Optional[int] = None
    max_hp: Optional[int] = None
    gold: Optional[int] = None
    energy: Optional[int] = None
    deck: Optional[List[str]] = None
    upgraded_cards: Optional[List[str]] = None
    relics: Optional[List[str]] = None
    potions: Optional[List[str]] = None
    combat_state: Optional[Dict[str, Any]] = None
    enemies: Optional[List[Dict[str, Any]]] = None
    hand_cards: Optional[List[str]] = None
    draw_pile: Optional[List[str]] = None
    discard_pile: Optional[List[str]] = None
    map_options: Optional[List[Dict[str, Any]]] = None
    boss: Optional[str] = None


class ModStatePayload(BaseModel):
    run_id: Optional[str] = None
    current_screen: Optional[str] = None
    character_class: str = "silent"
    ascension_level: int = 0
    act: int = 1
    current_floor: int = 1
    current_hp: int = 70
    max_hp: int = 70
    gold: int = 99
    energy: int = 3
    deck: List[str] = []
    upgraded_cards: List[str] = []
    relics: List[str] = []
    potions: List[str] = []
    combat_state: Dict[str, Any] = {}
    enemies: List[Dict[str, Any]] = []
    hand_cards: List[str] = []
    draw_pile: List[str] = []
    discard_pile: List[str] = []
    map_options: List[Dict[str, Any]] = []
    boss: Optional[str] = None


class RecommendationRequest(BaseModel):
    run_id: str
    query_type: str = Field(pattern="^(card_pick|relic_pick|shop|pathing|combat)$")
    options: List[str] = []
    user_query: str = ""


class ModRecommendationRequest(BaseModel):
    state: ModStatePayload
    query_type: str = Field(pattern="^(card_pick|relic_pick|shop|pathing|combat)$")
    options: List[str] = []
    user_query: str = ""


class RecommendationResponse(BaseModel):
    recommendation: str
    reasoning: str
    scene_type: str = ""
    explanation_panel: Dict[str, Any] = {}
    option_scores: List[Dict[str, Any]]
    graph_context: List[Dict[str, Any]]
    risk_report: Dict[str, Any]
    latency_ms: float
    backend: str
    debug: Dict[str, Any] = {}
    localized: Dict[str, Any] = {}


def default_state(run_id: str, req: StartRunRequest) -> Dict[str, Any]:
    return {
        "run_id": run_id,
        "source": req.source,
        "game": "sts1",
        "patch_version": kb.metadata.get("patch_version", "unknown"),
        "character_class": req.character_class.lower(),
        "ascension_level": req.ascension_level,
        "act": 1,
        "current_floor": 1,
        "current_hp": req.max_hp,
        "max_hp": req.max_hp,
        "gold": 99,
        "energy": 3,
        "deck": ["Strike", "Defend"],
        "upgraded_cards": [],
        "relics": [],
        "potions": [],
        "combat_state": {},
        "enemies": [],
        "hand_cards": [],
        "draw_pile": [],
        "discard_pile": [],
        "map_options": [],
    }


async def broadcast(payload: Dict[str, Any]) -> None:
    disconnected = []
    for websocket in subscribers:
        try:
            await websocket.send_json(payload)
        except Exception:
            disconnected.append(websocket)
    for websocket in disconnected:
        if websocket in subscribers:
            subscribers.remove(websocket)


def normalize_mod_state(payload: ModStatePayload) -> Dict[str, Any]:
    run_id = payload.run_id or "mod_live"
    state = payload.model_dump()
    character_class = state.get("character_class", "silent").lower()
    state["raw_deck"] = list(state.get("deck", []))
    state["raw_relics"] = list(state.get("relics", []))
    state["raw_potions"] = list(state.get("potions", []))
    state["raw_hand_cards"] = list(state.get("hand_cards", []))
    state["deck"] = normalize_entity_list(state.get("deck", []), character_class)
    state["relics"] = normalize_entity_list(state.get("relics", []), character_class)
    state["potions"] = normalize_entity_list(state.get("potions", []), character_class)
    state["hand_cards"] = normalize_entity_list(state.get("hand_cards", []), character_class)
    state["draw_pile"] = normalize_entity_list(state.get("draw_pile", []), character_class)
    state["discard_pile"] = normalize_entity_list(state.get("discard_pile", []), character_class)
    state.update(
        {
            "run_id": run_id,
            "source": "mod_bridge",
            "game": "sts1",
            "patch_version": kb.metadata.get("patch_version", "unknown"),
            "character_class": character_class,
        }
    )
    return with_localized_state(state)


def normalize_entity_list(values: List[str], character_class: str) -> List[str]:
    normalized = []
    for value in values:
        entity_id = kb.resolve_id(str(value), character_class)
        if entity_id:
            normalized.append(entity_id)
    return normalized


def normalize_option_list(values: List[str], character_class: str) -> List[str]:
    normalized = []
    for value in values:
        text = str(value)
        entity_id = kb.resolve_id(text, character_class)
        normalized.append(entity_id or text)
    return normalized


def scene_type_for_state(state: Dict[str, Any]) -> str:
    query_type = state.get("query_type", "")
    current_screen = str(state.get("current_screen") or "").upper()
    if query_type == "card_pick":
        return "card_reward"
    if query_type == "shop":
        return "shop"
    if query_type == "pathing":
        return "map"
    if query_type == "combat":
        return "combat"
    if query_type == "relic_pick":
        if "BOSS" in current_screen:
            return "boss_relic"
        return "relic_reward"
    return query_type or "unknown"


def grade_for_score(score: Any) -> str:
    try:
        value = float(score)
    except (TypeError, ValueError):
        value = 0.0
    if value >= 90:
        return "S"
    if value >= 78:
        return "A"
    if value >= 65:
        return "B"
    if value >= 50:
        return "C"
    if value >= 35:
        return "D"
    return "F"


def score_breakdown(score: Dict[str, Any]) -> Dict[str, Any]:
    reasons = score.get("reasons", []) or []
    risks = score.get("risks", []) or []
    return {
        "base_strength": score.get("score", 0),
        "strategy_fit": score.get("strategy_signal", 0),
        "synergy": len(score.get("evidence", []) or []),
        "risk_coverage": sum(1 for reason in reasons if any(word in reason.lower() for word in ("risk", "cover", "aoe", "defense", "frontload"))),
        "risk_penalty": len(risks),
        "confidence": score.get("confidence", 0),
    }


def enrich_option_scores(option_scores: List[Dict[str, Any]], explanation_panel: Dict[str, Any]) -> List[Dict[str, Any]]:
    comparisons = {
        item.get("option_id"): item
        for item in explanation_panel.get("candidate_comparison", [])
        if item.get("option_id")
    }
    enriched = []
    for score in option_scores:
        item = dict(score)
        grade = grade_for_score(item.get("score"))
        item["grade"] = grade
        item["display_badge"] = f"{grade} {item.get('score', 0)}"
        item["score_breakdown"] = score_breakdown(item)
        item["why_not"] = comparisons.get(item.get("option_id"), {}).get("why_not", "")
        enriched.append(item)
    return enriched


def response_debug(state: Dict[str, Any], final_state: Dict[str, Any], scene_type: str) -> Dict[str, Any]:
    warnings = []
    if not state.get("options") and scene_type not in {"combat", "map"}:
        warnings.append("No explicit decision options were provided.")
    if scene_type == "map" and not state.get("options") and not state.get("map_options"):
        warnings.append("No map_options were available for pathing.")
    return {
        "query_type": state.get("query_type", ""),
        "scene_type": scene_type,
        "options_count": len(state.get("options") or []),
        "map_options_count": len(state.get("map_options") or []),
        "current_screen": state.get("current_screen", ""),
        "latency_ms": final_state.get("latency_ms", 0.0),
        "backend": "neo4j_or_local_fallback",
        "normalization_warnings": warnings,
    }


def record_mod_event(event: Dict[str, Any]) -> None:
    global mod_last_error
    if event.get("error"):
        mod_last_error = event["error"]
    mod_diagnostics.appendleft(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **event,
        }
    )


def build_recommendation_response(current_state: Dict[str, Any]) -> RecommendationResponse:
    if current_state.get("query_type") == "pathing" and not current_state.get("options"):
        current_state = dict(current_state)
        current_state["options"] = list(current_state.get("map_options") or [])
    started_at = time.perf_counter()
    final_state = engine.invoke(current_state)
    scene_type = scene_type_for_state(current_state)
    option_scores = enrich_option_scores(
        final_state.get("option_scores", []),
        final_state.get("explanation_panel", {}),
    )
    final_state["option_scores"] = option_scores
    latency_ms = final_state.get("latency_ms", round((time.perf_counter() - started_at) * 1000, 2))
    response = RecommendationResponse(
        recommendation=final_state.get("recommendation", "skip"),
        reasoning=final_state.get("reasoning", ""),
        scene_type=scene_type,
        explanation_panel=final_state.get("explanation_panel", {}),
        option_scores=option_scores,
        graph_context=final_state.get("graph_context", []),
        risk_report=final_state.get("risk_report", {}),
        latency_ms=latency_ms,
        backend="neo4j_or_local_fallback",
        debug=response_debug(current_state, final_state, scene_type),
    )
    response.localized = {"zh": localize_response(response.model_dump())}
    return response


@app.get("/")
def index():
    index_path = WEB_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Slay the Spire Agentic GraphRAG API is running."}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "knowledge_base": kb.entity_counts(),
        "graph_backend": getattr(engine, "backend", "langgraph"),
    }


@app.post("/start_run")
async def start_run(req: StartRunRequest):
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    state = default_state(run_id, req)
    state = with_localized_state(state)
    active_runs[run_id] = state
    await broadcast({"type": "state_updated", "run_id": run_id, "state": state})
    return {"message": "Run started", "run_id": run_id, "state": state}


@app.post("/update_state")
async def update_state(req: UpdateStateRequest):
    if req.run_id not in active_runs:
        raise HTTPException(status_code=404, detail="Run ID not found")
    state = active_runs[req.run_id]
    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key != "run_id":
            state[key] = value
    state = with_localized_state(state)
    active_runs[req.run_id] = state
    await broadcast({"type": "state_updated", "run_id": req.run_id, "state": state})
    return {"message": "State updated", "current_state": state}


@app.post("/mod/state")
async def mod_state(payload: ModStatePayload):
    state = normalize_mod_state(payload)
    run_id = state["run_id"]
    active_runs[run_id] = state
    record_mod_event(
        {
            "kind": "state",
            "run_id": run_id,
            "current_screen": state.get("current_screen", ""),
            "query_type": "",
            "scene_type": "",
            "options_count": 0,
            "latency_ms": 0.0,
            "top_recommendation": "",
            "error": "",
        }
    )
    await broadcast({"type": "state_updated", "run_id": run_id, "state": state})
    return {"message": "Mod state accepted", "run_id": run_id, "state": state}


@app.post("/mod/recommend")
async def mod_recommend(req: ModRecommendationRequest):
    started_at = time.perf_counter()
    state = normalize_mod_state(req.state)
    run_id = state["run_id"]
    state["query_type"] = req.query_type
    state["options"] = normalize_option_list(req.options, state["character_class"])
    if req.query_type == "pathing" and not state["options"]:
        state["options"] = list(state.get("map_options") or [])
    state["raw_options"] = list(req.options)
    state["user_query"] = req.user_query
    state = with_localized_state(state)
    active_runs[run_id] = state
    await broadcast({"type": "state_updated", "run_id": run_id, "state": state})

    current_state = state.copy()
    current_state.update(
        {
            "query_type": req.query_type,
            "options": state["options"],
            "user_query": req.user_query,
        }
    )
    response = build_recommendation_response(current_state)
    record_mod_event(
        {
            "kind": "recommendation",
            "run_id": run_id,
            "current_screen": state.get("current_screen", ""),
            "query_type": req.query_type,
            "scene_type": response.scene_type,
            "options_count": len(state.get("options") or []),
            "map_options_count": len(state.get("map_options") or []),
            "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
            "top_recommendation": response.recommendation,
            "error": "" if response.option_scores else "No option_scores returned.",
        }
    )
    await broadcast({"type": "recommendation", "run_id": run_id, "response": response.model_dump()})
    return {"message": "Mod recommendation generated", "run_id": run_id, "state": state, "recommendation": response}


@app.get("/mod/diagnostics")
def mod_diagnostics_endpoint():
    latest = mod_diagnostics[0] if mod_diagnostics else {}
    return {
        "status": "ok",
        "api_healthy": True,
        "last_error": mod_last_error or "",
        "current_run_id": latest.get("run_id", ""),
        "scene_type": latest.get("scene_type", ""),
        "query_type": latest.get("query_type", ""),
        "options_count": latest.get("options_count", 0),
        "events": list(mod_diagnostics),
    }


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    if run_id not in active_runs:
        raise HTTPException(status_code=404, detail="Run ID not found")
    return active_runs[run_id]


@app.get("/mod/live")
def get_live_mod_state():
    state = active_runs.get("mod_live")
    if not state:
        raise HTTPException(status_code=404, detail="No live Mod state has been received yet")
    return {
        "run_id": "mod_live",
        "state": state,
        "has_decision": bool(state.get("query_type") and (state.get("options") or state.get("query_type") == "combat")),
        "query_type": state.get("query_type"),
        "options": state.get("options", []),
        "raw_options": state.get("raw_options", []),
    }


@app.post("/get_recommendation", response_model=RecommendationResponse)
async def get_recommendation(req: RecommendationRequest):
    if req.run_id not in active_runs:
        raise HTTPException(status_code=404, detail="Run ID not found")
    current_state = active_runs[req.run_id].copy()
    options = normalize_option_list(req.options, current_state.get("character_class", ""))
    if req.query_type == "combat" and not options:
        options = current_state.get("hand_cards", [])
    if req.query_type == "pathing" and not options:
        options = list(current_state.get("map_options") or [])
    current_state.update(
        {
            "query_type": req.query_type,
            "options": options,
            "user_query": req.user_query,
        }
    )
    response = build_recommendation_response(current_state)
    await broadcast({"type": "recommendation", "run_id": req.run_id, "response": response.model_dump()})
    return response


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    subscribers.append(websocket)
    try:
        await websocket.send_json({"type": "connected", "active_runs": list(active_runs.keys())})
        for run_id, state in active_runs.items():
            await websocket.send_json({"type": "state_updated", "run_id": run_id, "state": state})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in subscribers:
            subscribers.remove(websocket)
