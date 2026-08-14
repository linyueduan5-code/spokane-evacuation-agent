import os

os.environ["AGENT_PROVIDER"] = "deterministic"
os.environ["ROUTING_PROVIDER"] = "replay"

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def demo_payload(at="2026-08-01T20:00:00-07:00"):
    return {
        "session_id": "test-session",
        "message": "Analyze my situation and find a safe shelter",
        "context": {
            "address": "Rifle Club Road, Spokane, WA",
            "lat": 47.753,
            "lon": -117.512,
            "at": at,
            "needs": {"pets": True, "mobility": True, "medical": False, "service_animal": False},
            "contact": "demo@example.invalid",
            "consent_to_search": False,
        },
    }


def test_health_reports_exactly_seven_tools():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["tool_count"] == 7


def test_level_three_keeps_accessibility_and_pet_constraints():
    response = client.post("/api/chat", json=demo_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["severity"] == "danger"
    assert body["map_state"]["evacuation"]["level"] == 3
    shelter = body["map_state"]["selected_shelter"]
    assert shelter["accepts"]["pets"] is True
    assert shelter["accepts"]["mobility"] is True
    assert shelter["name"] == "Spokane Fair & Expo Center"
    convention = next(item for item in body["map_state"]["shelters"] if item["name"] == "Spokane Convention Center")
    assert convention["route_status"] == "detour_required"
    names = [step["tool"] for step in body["steps"]]
    assert names == [
        "get_evacuation_status", "get_active_incidents", "find_shelters",
        "check_hazmat_clearance", "send_notification",
    ]


def test_conflict_is_visible_and_official_level_wins():
    body = client.post("/api/chat", json=demo_payload()).json()
    evacuation = body["map_state"]["evacuation"]
    assert evacuation["level"] == 3
    assert evacuation["conflicts"]
    assert any("Conflicting" in notice for notice in body["notices"])


def test_missing_person_requires_consent():
    payload = {
        "session_id": "privacy-test",
        "name": "Avery Chen",
        "last_known_location": "Convention Center",
        "contact": "demo@example.invalid",
        "consent": False,
        "context": demo_payload()["context"],
    }
    body = client.post("/api/missing-person", json=payload).json()
    assert body["steps"][0]["status"] == "warning"
    assert len(body["steps"]) == 1


def test_synthetic_match_uses_all_three_reunification_tools():
    payload = {
        "session_id": "match-test",
        "name": "Avery Chen",
        "last_known_location": "Rifle Club Road",
        "contact": "demo@example.invalid",
        "consent": True,
        "context": demo_payload()["context"],
    }
    body = client.post("/api/missing-person", json=payload).json()
    assert [step["tool"] for step in body["steps"]] == [
        "file_missing_person", "search_missing_reports", "send_notification",
    ]
    assert "合成" in body["answer"]


def test_downgrade_does_not_imply_hazmat_clearance():
    body = client.post("/api/chat", json=demo_payload("2026-08-07T12:00:00-07:00")).json()
    assert body["map_state"]["evacuation"]["level"] == 2
    hazmat = next(step for step in body["steps"] if step["tool"] == "check_hazmat_clearance")
    assert hazmat["output"]["cleared"] is False
    assert "will not recommend returning home" in body["answer"]


def test_location_outside_evacuation_polygon_returns_safe_unknown_instead_of_500():
    payload = demo_payload()
    payload["context"].update({
        "address": "334 W Spokane Falls Blvd, Spokane, WA",
        "lat": 47.660899,
        "lon": -117.412441,
    })
    body = client.post("/api/chat", json=payload)
    assert body.status_code == 200
    result = body.json()
    assert result["map_state"]["evacuation"]["level"] is None
    assert result["map_state"]["evacuation"]["provenance"] is None
    assert "does not mean the area is safe" in result["answer"]
