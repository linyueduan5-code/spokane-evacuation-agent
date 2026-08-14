import json

from app.deepseek_agent import DeepSeekEvacuationAgent
from app.models import ChatRequest


def payload():
    return ChatRequest.model_validate({
        "session_id": "deepseek-test",
        "message": "I have two dogs and a wheelchair user. Where should we go?",
        "context": {
            "address": "Rifle Club Road, Spokane, WA",
            "lat": 47.753,
            "lon": -117.512,
            "at": "2026-08-01T20:00:00-07:00",
            "needs": {"pets": True, "mobility": True, "medical": False, "service_animal": False},
            "contact": "demo@example.invalid",
        },
    })


def completion_with_tools(*names):
    return {
        "choices": [{"message": {
            "role": "assistant", "content": None,
            "tool_calls": [
                {
                    "id": f"call-{index}", "type": "function",
                    "function": {"name": name, "arguments": json.dumps({})},
                }
                for index, name in enumerate(names)
            ],
        }}]
    }


def test_model_selects_tools_and_guard_fills_omissions(monkeypatch):
    agent = DeepSeekEvacuationAgent()
    agent.api_key = "test-only"
    responses = iter([
        completion_with_tools("get_evacuation_status", "find_shelters"),
        {"choices": [{"message": {"role": "assistant", "content": "done"}}]},
    ])
    monkeypatch.setattr(agent, "_completion", lambda messages, tools=None: next(responses))
    result = agent.chat(payload())
    assert result.orchestration["provider"] == "deepseek"
    assert result.orchestration["model_tool_calls"] == 2
    assert result.orchestration["guard_tool_calls"] == 3
    origins = {step.tool: step.origin for step in result.steps}
    assert origins["get_evacuation_status"] == "model"
    assert origins["find_shelters"] == "model"
    assert origins["get_active_incidents"] == "safety_guard"
    assert origins["check_hazmat_clearance"] == "safety_guard"
    assert origins["send_notification"] == "safety_guard"
    assert result.severity == "danger"


def test_model_failure_uses_safe_deterministic_completion(monkeypatch):
    agent = DeepSeekEvacuationAgent()
    agent.api_key = "test-only"
    monkeypatch.setattr(agent, "_completion", lambda messages, tools=None: (_ for _ in ()).throw(ValueError("bad payload")))
    result = agent.chat(payload())
    assert result.orchestration["model_error"] == "ValueError"
    assert result.orchestration["guard_tool_calls"] == 5
    assert result.map_state["evacuation"]["level"] == 3


def test_model_flow_handles_location_outside_evacuation_polygon(monkeypatch):
    agent = DeepSeekEvacuationAgent()
    agent.api_key = "test-only"
    request = payload()
    request.context.address = "334 W Spokane Falls Blvd, Spokane, WA"
    request.context.lat = 47.660899
    request.context.lon = -117.412441
    responses = iter([
        completion_with_tools("get_evacuation_status"),
        {"choices": [{"message": {"role": "assistant", "content": "done"}}]},
    ])
    monkeypatch.setattr(agent, "_completion", lambda messages, tools=None: next(responses))
    result = agent.chat(request)
    assert result.map_state["evacuation"]["level"] is None
    assert result.map_state["evacuation"]["provenance"] is None
    assert result.severity == "warning"
