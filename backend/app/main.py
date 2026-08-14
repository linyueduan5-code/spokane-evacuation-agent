from __future__ import annotations

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .agent import EvacuationAgent
from .dataset import EVACUATION_SNAPSHOTS, INCIDENT_SNAPSHOTS, ROAD_CLOSURES, SHELTERS, SOURCE_REGISTRY
from .deepseek_agent import DeepSeekEvacuationAgent
from .evaluation import load_dataset, run_evaluation, score_decision
from .geocoding import MapboxGeocoder
from .models import ChatRequest, ChatResponse, EvaluationDecisionRequest, MissingPersonRequest


load_dotenv(Path(__file__).resolve().parents[2] / ".env")

app = FastAPI(
    title="Spokane Evacuation Agent MVP",
    version="0.1.0",
    description="One agent orchestrating seven tools over official-source replay and synthetic personal data.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
provider = os.getenv("AGENT_PROVIDER", "deterministic").lower()
agent = DeepSeekEvacuationAgent() if provider == "deepseek" else EvacuationAgent()
geocoder = MapboxGeocoder()


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "agent": "single-orchestrator",
        "tool_count": 7,
        "data_mode": "replay",
        "provider": "deepseek" if isinstance(agent, DeepSeekEvacuationAgent) else "deterministic",
        "model": getattr(agent, "model", None),
        "model_configured": getattr(agent, "enabled", False),
        "routing_provider": agent.tools.router.provider,
        "routing_configured": agent.tools.router.enabled,
        "geocoding_provider": "mapbox" if geocoder.enabled else "disabled",
    }


@app.get("/api/geocode")
def geocode(q: str = Query(min_length=3, max_length=120)) -> dict:
    if not geocoder.enabled:
        raise HTTPException(status_code=503, detail="Address search is not configured")
    try:
        return {"results": list(geocoder.search(q))}
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Address search is temporarily unavailable") from exc


@app.get("/api/bootstrap")
def bootstrap() -> dict:
    return {
        "scenario": {
            "name": "Rifle Club Road household",
            "address": "Rifle Club Road, Spokane, WA",
            "lat": 47.753,
            "lon": -117.512,
            "timeline": [
                "2026-08-01T20:00:00-07:00",
                "2026-08-06T12:00:00-07:00",
                "2026-08-07T12:00:00-07:00",
                "2026-08-08T20:00:00-07:00",
            ],
            "needs": {"pets": True, "mobility": True, "medical": False, "service_animal": False},
        },
        "sources": SOURCE_REGISTRY,
        "map": {
            "evacuation_zones": EVACUATION_SNAPSHOTS,
            "incidents": INCIDENT_SNAPSHOTS,
            "shelters": SHELTERS,
            "road_closures": ROAD_CLOSURES,
        },
        "privacy": "Missing-person and shelter check-in records are synthetic and stored in memory only.",
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    return agent.chat(request)


@app.post("/api/missing-person", response_model=ChatResponse)
def missing_person(request: MissingPersonRequest) -> ChatResponse:
    return agent.missing_person(request)


@app.get("/api/evaluation/scenarios")
def evaluation_scenarios() -> dict:
    return load_dataset()


@app.post("/api/evaluation/run")
def evaluation_run() -> dict:
    return run_evaluation()


@app.post("/api/evaluation/score")
def evaluation_score(request: EvaluationDecisionRequest) -> dict:
    scenarios = load_dataset()["scenarios"]
    scenario = next((item for item in scenarios if item["scenario_id"] == request.scenario_id), None)
    if scenario is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Evaluation scenario not found")
    return score_decision(scenario, request.decision.model_dump())
