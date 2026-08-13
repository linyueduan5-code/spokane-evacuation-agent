import os
from copy import deepcopy

os.environ["AGENT_PROVIDER"] = "deterministic"

from fastapi.testclient import TestClient

from app.evaluation import baseline_decision, load_dataset, run_evaluation, score_decision
from app.main import app


client = TestClient(app)


def scenario(category: str) -> dict:
    return next(item for item in load_dataset()["scenarios"] if item["category"] == category)


def test_dataset_has_40_unique_synthetic_scenarios_across_8_categories():
    dataset = load_dataset()
    assert dataset["count"] == 40
    assert len(dataset["scenarios"]) == 40
    assert len({item["scenario_id"] for item in dataset["scenarios"]}) == 40
    assert len({item["category"] for item in dataset["scenarios"]}) == 8
    assert all(item["synthetic"] is True for item in dataset["scenarios"])


def test_baseline_passes_all_safety_gates():
    report = run_evaluation()
    assert report["summary"]["passed"] == 40
    assert report["summary"]["hard_safety_violations"] == 0
    assert report["summary"]["average_score"] == 100


def test_negative_control_catches_unsafe_route():
    case = scenario("closure_reroute")
    bad = baseline_decision(case)
    bad.update({"route_id": "r-short-closed", "shelter_id": "blocked"})
    result = score_decision(case, bad)
    assert result["safety_passed"] is False
    assert result["score"] == 0
    assert any(item["code"] == "unsafe_route" for item in result["violations"])


def test_negative_control_catches_ignored_accessibility_need():
    case = scenario("accessibility")
    bad = baseline_decision(case)
    bad.update({"route_id": "r-near", "shelter_id": "incompatible"})
    result = score_decision(case, bad)
    assert any(item["code"] == "hard_need_ignored" for item in result["violations"])


def test_negative_control_catches_unsafe_reentry():
    case = next(
        item for item in load_dataset()["scenarios"]
        if item["category"] == "reentry" and item["hazmat"]["cleared"] is False
    )
    bad = deepcopy(baseline_decision(case))
    bad["action"] = "reentry_allowed"
    result = score_decision(case, bad)
    assert any(item["code"] == "unsafe_reentry" for item in result["violations"])


def test_evaluation_api_returns_summary_and_case_details():
    response = client.post("/api/evaluation/run")
    assert response.status_code == 200
    body = response.json()
    assert body["dataset"]["scenario_count"] == 40
    assert len(body["categories"]) == 8
    assert len(body["results"]) == 40


def test_score_api_can_grade_future_agent_outputs():
    case = scenario("closure_reroute")
    decision = baseline_decision(case)
    response = client.post("/api/evaluation/score", json={"scenario_id": case["scenario_id"], "decision": decision})
    assert response.status_code == 200
    assert response.json()["score"] == 100
