from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Needs(BaseModel):
    pets: bool = False
    mobility: bool = False
    medical: bool = False
    service_animal: bool = False


class UserContext(BaseModel):
    address: str = "Rifle Club Road, Spokane, WA"
    lat: float = 47.753
    lon: float = -117.512
    at: str = "2026-08-01T20:00:00-07:00"
    needs: Needs = Field(default_factory=Needs)
    contact: str = "demo@example.invalid"
    consent_to_search: bool = False


class ChatRequest(BaseModel):
    session_id: str = "demo-session"
    message: str
    context: UserContext = Field(default_factory=UserContext)


class ToolStep(BaseModel):
    tool: str
    status: Literal["ok", "warning", "blocked"] = "ok"
    origin: Literal["model", "safety_guard", "deterministic"] = "deterministic"
    input: dict[str, Any]
    output: dict[str, Any] | list[Any]
    elapsed_ms: int = 0


class ChatResponse(BaseModel):
    session_id: str
    intent: str
    answer: str
    severity: Literal["info", "warning", "danger"] = "info"
    steps: list[ToolStep]
    map_state: dict[str, Any]
    notices: list[str] = Field(default_factory=list)
    orchestration: dict[str, Any] = Field(default_factory=dict)


class MissingPersonRequest(BaseModel):
    session_id: str = "demo-session"
    name: str
    last_known_location: str
    contact: str
    consent: bool
    context: UserContext = Field(default_factory=UserContext)


class EvaluationDecision(BaseModel):
    action: str
    shelter_id: str | None = None
    route_id: str | None = None
    escalate: bool = False
    flags: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    tool_calls: int = 0
    explanation: str = ""


class EvaluationDecisionRequest(BaseModel):
    scenario_id: str
    decision: EvaluationDecision
