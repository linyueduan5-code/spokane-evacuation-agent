from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .agent import EvacuationAgent
from .models import ChatRequest, ChatResponse, ToolStep


SYSTEM_PROMPT = """You are the tool-selection orchestrator for a wildfire evacuation demo.
Your only job is to choose and call tools. Never invent evacuation levels, routes,
shelter capabilities, clearances, matches, or notification results.

For an evacuation-plan request, call get_evacuation_status first. Then obtain active
incidents, shelters, and hazmat clearance. Level 3 means immediate evacuation, but
you must still preserve pet, mobility, medical, and service-animal constraints.
Missing or stale data is never an all-clear. All notifications are simulated.
Missing-person tools require explicit consent. Use tool results, then provide a short
Chinese summary. A deterministic safety guard will validate the result.
"""


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_evacuation_status",
            "description": "Get the official evacuation level for the user's supplied location and replay time.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_incidents",
            "description": "Find active wildfire incidents near the supplied location.",
            "parameters": {
                "type": "object",
                "properties": {"radius_km": {"type": "number", "minimum": 1, "maximum": 100}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_shelters",
            "description": "Find open, reachable shelters satisfying every hard household need.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_hazmat_clearance",
            "description": "Check whether the location has explicit hazardous-material re-entry clearance.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_missing_person",
            "description": "Create a synthetic in-memory missing-person demo report only with explicit consent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "last_known_location": {"type": "string"},
                },
                "required": ["name", "last_known_location"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_missing_reports",
            "description": "Search only synthetic shelter check-ins for a consented missing-person demo.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_notification",
            "description": "Send a simulated notification. It never contacts an external service.",
            "parameters": {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
                "additionalProperties": False,
            },
        },
    },
]


class DeepSeekEvacuationAgent(EvacuationAgent):
    """DeepSeek chooses tools; deterministic code remains the safety authority."""

    REQUIRED_PLAN_TOOLS = (
        "get_evacuation_status",
        "get_active_incidents",
        "find_shelters",
        "check_hazmat_clearance",
    )

    def __init__(self) -> None:
        super().__init__()
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        self.timeout_seconds = float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "45"))

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.model)

    def _completion(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "stream": False,
            "thinking": {"type": "disabled"},
        }
        if tools:
            payload.update({"tools": tools, "tool_choice": "auto"})
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _assistant_message(message: dict) -> dict:
        clean = {"role": "assistant", "content": message.get("content")}
        if message.get("tool_calls"):
            clean["tool_calls"] = message["tool_calls"]
        return clean

    def _execute_tool(
        self,
        name: str,
        arguments: dict,
        request: ChatRequest,
        outputs: dict[str, Any],
        origin: str,
    ) -> ToolStep:
        ctx = request.context
        if name == "get_evacuation_status":
            payload = {"address": ctx.address, "lat": ctx.lat, "lon": ctx.lon, "at": ctx.at}
            step = self._call(name, self.tools.get_evacuation_status, payload, origin)
        elif name == "get_active_incidents":
            payload = {"lat": ctx.lat, "lon": ctx.lon, "radius_km": float(arguments.get("radius_km", 35)), "at": ctx.at}
            step = self._call(name, self.tools.get_active_incidents, payload, origin)
        elif name == "find_shelters":
            payload = {"lat": ctx.lat, "lon": ctx.lon, "needs": ctx.needs, "at": ctx.at}
            step = self._call(name, self.tools.find_shelters, payload, origin)
        elif name == "check_hazmat_clearance":
            evacuation = outputs.get("get_evacuation_status", {})
            payload = {"address": ctx.address, "zone_name": evacuation.get("zone_name"), "at": ctx.at}
            step = self._call(name, self.tools.check_hazmat_clearance, payload, origin)
        elif name == "file_missing_person":
            payload = {
                "session_id": request.session_id, "name": arguments.get("name", ""),
                "last_known_location": arguments.get("last_known_location", ""),
                "contact": ctx.contact, "consent": ctx.consent_to_search,
            }
            step = self._call(name, self.tools.file_missing_person, payload, origin)
            step.input["contact"] = "masked"
        elif name == "search_missing_reports":
            payload = {
                "session_id": request.session_id, "name": arguments.get("name", ""),
                "consent": ctx.consent_to_search,
            }
            step = self._call(name, self.tools.search_missing_reports, payload, origin)
        elif name == "send_notification":
            payload = {
                "session_id": request.session_id, "contact": ctx.contact,
                "message": arguments.get("message", "Synthetic evacuation demo notification."),
            }
            step = self._call(name, self.tools.send_notification, payload, origin)
            step.input["contact"] = "masked"
        else:
            step = ToolStep(
                tool=name, status="blocked", origin=origin, input=arguments,
                output={"error": "Unknown tool rejected by dispatcher."}, elapsed_ms=0,
            )
        outputs[name] = step.output
        return step

    def chat(self, request: ChatRequest) -> ChatResponse:
        if not self.enabled:
            fallback = super().chat(request)
            fallback.notices.insert(0, "DeepSeek is not configured; deterministic fallback is active.")
            return fallback

        safe_context = {
            "address": request.context.address,
            "lat": request.context.lat,
            "lon": request.context.lon,
            "replay_time": request.context.at,
            "needs": request.context.needs.model_dump(),
            "data_mode": "synthetic_replay",
        }
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Request: {request.message}\nContext JSON: {json.dumps(safe_context)}"},
        ]
        steps: list[ToolStep] = []
        outputs: dict[str, Any] = {}
        model_error = None
        model_summary = None
        try:
            for _ in range(6):
                completion = self._completion(messages, TOOL_SCHEMAS)
                message = completion["choices"][0]["message"]
                messages.append(self._assistant_message(message))
                calls = message.get("tool_calls") or []
                if not calls:
                    model_summary = message.get("content")
                    break
                for call in calls:
                    function = call.get("function", {})
                    name = function.get("name", "")
                    try:
                        arguments = json.loads(function.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        arguments = {}
                    step = self._execute_tool(name, arguments, request, outputs, "model")
                    steps.append(step)
                    messages.append({
                        "role": "tool", "tool_call_id": call["id"],
                        "content": json.dumps(step.output, ensure_ascii=False, default=str),
                    })
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            model_error = type(exc).__name__

        model_called = {step.tool for step in steps if step.origin == "model"}
        for name in self.REQUIRED_PLAN_TOOLS:
            if name not in outputs:
                steps.append(self._execute_tool(name, {}, request, outputs, "safety_guard"))

        evac = outputs.get("get_evacuation_status", {})
        incidents = outputs.get("get_active_incidents", [])
        shelters = outputs.get("find_shelters", [])
        hazmat = outputs.get("check_hazmat_clearance", {})
        level = evac.get("level") if isinstance(evac, dict) else None
        if level == 3 and "send_notification" not in outputs:
            steps.append(self._execute_tool(
                "send_notification",
                {"message": f"Level 3 evacuation for {request.context.address}: leave now."},
                request, outputs, "safety_guard",
            ))

        answer, severity = self._compose(
            level,
            evac if isinstance(evac, dict) else {},
            incidents if isinstance(incidents, list) else [],
            shelters if isinstance(shelters, list) else [],
            hazmat if isinstance(hazmat, dict) else {},
            request.context.needs.model_dump(),
        )
        guard_count = sum(step.origin == "safety_guard" for step in steps)
        notices = [
            f"DeepSeek {self.model} selected {len(model_called)} distinct tool(s); safety guard added {guard_count} call(s).",
            "Resident-facing safety conclusions are composed deterministically from tool outputs.",
            "Decision-support demo only. Follow 911 and official incident-command instructions.",
            "All personal, shelter-capability, and check-in data in this demo is synthetic.",
        ]
        if model_error:
            notices.insert(0, f"DeepSeek call failed ({model_error}); deterministic safety fallback completed the plan.")
        if evac.get("conflicts"):
            notices.append("Conflicting evacuation records were detected; the official, more conservative level was selected.")
        if evac.get("provenance", {}).get("stale"):
            notices.append("Evacuation data is stale. The agent will not infer an all-clear.")
        selected_shelter = shelters[0] if isinstance(shelters, list) and shelters else None
        return ChatResponse(
            session_id=request.session_id,
            intent="model_tool_orchestration",
            answer=answer,
            severity=severity,
            steps=steps,
            map_state={
                "center": [request.context.lat, request.context.lon],
                "user": {"lat": request.context.lat, "lon": request.context.lon, "address": request.context.address},
                "evacuation": evac,
                "incidents": incidents,
                "shelters": shelters,
                "selected_shelter": selected_shelter,
            },
            notices=notices,
            orchestration={
                "provider": "deepseek",
                "model": self.model,
                "model_tool_calls": sum(step.origin == "model" for step in steps),
                "guard_tool_calls": guard_count,
                "model_summary_generated": bool(model_summary),
                "model_error": model_error,
            },
        )

