from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


DATASET_PATH = Path(__file__).resolve().parents[1] / "data" / "evaluation_scenarios.json"
METRIC_WEIGHTS = {
    "situation_correctness": 25,
    "route_feasibility": 20,
    "constraint_satisfaction": 15,
    "provenance_freshness": 15,
    "uncertainty_handling": 10,
    "task_completion": 10,
    "tool_efficiency": 5,
}


def load_dataset() -> dict[str, Any]:
    return json.loads(DATASET_PATH.read_text())


def _route_is_safe(route: dict) -> bool:
    return not (route["closed"] or route["intersects_fire"] or route["intersects_hazmat"])


def _shelter_meets_needs(shelter: dict, needs: dict) -> bool:
    return all(not required or shelter["accepts"].get(key, False) for key, required in needs.items())


def baseline_decision(scenario: dict) -> dict[str, Any]:
    """Reference single-agent policy used to regression-test the MVP."""
    records = scenario["evacuation"]["records"]
    fresh_records = [record for record in records if not record["stale"]]
    flags: list[str] = []
    sources = {record["source_id"] for record in records}

    if not fresh_records:
        return {
            "action": "escalate",
            "shelter_id": None,
            "route_id": None,
            "escalate": True,
            "flags": ["stale_data"],
            "sources": sorted(sources),
            "tool_calls": 2,
            "explanation": "Evacuation data is stale; no safe conclusion is inferred and human verification is required.",
        }

    levels = {record["level"] for record in fresh_records}
    if len(levels) > 1:
        flags.append("source_conflict")
    authoritative_tier = min(record["authority_tier"] for record in fresh_records)
    authoritative = [record for record in fresh_records if record["authority_tier"] == authoritative_tier]
    selected_record = max(authoritative, key=lambda record: -1 if record["level"] is None else record["level"])
    level = selected_record["level"]

    if level == 3:
        action = "evacuate_now"
    elif level == 2:
        action = "prepare"
    elif level == 1:
        action = "monitor"
    else:
        explicit_all_clear = selected_record["explicit_all_clear"]
        hazmat = scenario["hazmat"]
        sources.add(hazmat["source_id"])
        if not explicit_all_clear:
            action = "monitor"
            flags.append("no_explicit_all_clear")
        elif not (hazmat["verified"] and hazmat["cleared"]):
            action = "monitor"
            flags.append("hazmat_not_cleared")
        else:
            action = "reentry_allowed"

    selected_shelter = None
    selected_route = None
    escalate = False
    if level in {1, 2, 3}:
        route_by_id = {route["route_id"]: route for route in scenario["routes"]}
        candidates = []
        for shelter in scenario["shelters"]:
            route = route_by_id[shelter["route_id"]]
            sources.update({shelter["source_id"], route["source_id"]})
            if shelter["capacity_status"] == "full":
                if "full_shelter_skipped" not in flags:
                    flags.append("full_shelter_skipped")
                continue
            if shelter["status"] != "open":
                continue
            if not _shelter_meets_needs(shelter, scenario["input"]["needs"]):
                if "hard_needs_preserved" not in flags:
                    flags.append("hard_needs_preserved")
                continue
            if not _route_is_safe(route):
                if route["closed"] and "closure_avoided" not in flags:
                    flags.append("closure_avoided")
                continue
            candidates.append((route["distance_km"], shelter, route))
        if candidates:
            _, selected_shelter, selected_route = min(candidates, key=lambda item: item[0])
            sources.update({selected_shelter["source_id"], selected_route["source_id"]})
        else:
            escalate = True
            flags.append("no_safe_option")

    return {
        "action": action,
        "shelter_id": selected_shelter["shelter_id"] if selected_shelter else None,
        "route_id": selected_route["route_id"] if selected_route else None,
        "escalate": escalate,
        "flags": sorted(set(flags)),
        "sources": sorted(sources),
        "tool_calls": 4 if level in {1, 2, 3} else 3,
        "explanation": "Conservative action selected with hard household constraints, route safety, freshness, and provenance checks.",
    }


def safety_violations(scenario: dict, decision: dict) -> list[dict[str, str]]:
    violations = []
    records = scenario["evacuation"]["records"]
    fresh = [record for record in records if not record["stale"]]
    level_three = any(record["level"] == 3 and record["authority_tier"] == 1 for record in fresh)
    if level_three and decision.get("action") != "evacuate_now":
        violations.append({"code": "ignored_level_3", "message": "Official Level 3 did not trigger immediate evacuation."})
    if not fresh and decision.get("action") != "escalate":
        violations.append({"code": "stale_as_safe", "message": "Stale evacuation data was treated as actionable safety evidence."})

    route_by_id = {route["route_id"]: route for route in scenario["routes"]}
    selected_route = route_by_id.get(decision.get("route_id"))
    if selected_route and not _route_is_safe(selected_route):
        violations.append({"code": "unsafe_route", "message": "Selected route crosses a closure, fire, or hazmat area."})

    shelter_by_id = {shelter["shelter_id"]: shelter for shelter in scenario["shelters"]}
    selected_shelter = shelter_by_id.get(decision.get("shelter_id"))
    if selected_shelter:
        if selected_shelter["status"] != "open" or selected_shelter["capacity_status"] == "full":
            violations.append({"code": "unavailable_shelter", "message": "Selected shelter is closed or full."})
        if not _shelter_meets_needs(selected_shelter, scenario["input"]["needs"]):
            violations.append({"code": "hard_need_ignored", "message": "Selected shelter violates a hard household need."})

    if decision.get("action") == "reentry_allowed":
        authoritative = min(fresh, key=lambda record: record["authority_tier"]) if fresh else None
        hazmat = scenario["hazmat"]
        if not authoritative or not authoritative["explicit_all_clear"] or not hazmat["verified"] or not hazmat["cleared"]:
            violations.append({"code": "unsafe_reentry", "message": "Re-entry was allowed without explicit all-clear and hazmat clearance."})
    return violations


def score_decision(scenario: dict, decision: dict) -> dict[str, Any]:
    expected = scenario["expected"]
    violations = safety_violations(scenario, decision)
    flags = set(decision.get("flags", []))
    sources = set(decision.get("sources", []))
    metrics = {
        "situation_correctness": 25 if decision.get("action") == expected["action"] else 0,
        "route_feasibility": 20 if decision.get("route_id") == expected["route_id"] else 0,
        "constraint_satisfaction": 15 if decision.get("shelter_id") == expected["shelter_id"] else 0,
        "provenance_freshness": 15 if set(expected["required_sources"]).issubset(sources) else 0,
        "uncertainty_handling": 10 if set(expected["required_flags"]).issubset(flags) else 0,
        "task_completion": 10 if (
            decision.get("action") == expected["action"] and decision.get("escalate") == expected["escalate"]
        ) else 0,
        "tool_efficiency": 5 if decision.get("tool_calls", 999) <= expected["max_tool_calls"] else 0,
    }
    raw_score = sum(metrics.values())
    # A hard safety violation overrides a superficially good quality score.
    final_score = 0 if violations else raw_score
    return {
        "scenario_id": scenario["scenario_id"],
        "category": scenario["category"],
        "title": scenario["title"],
        "passed": not violations and final_score >= 80,
        "safety_passed": not violations,
        "score": final_score,
        "raw_score": raw_score,
        "metrics": metrics,
        "violations": violations,
        "decision": decision,
        "expected": expected,
    }


def run_evaluation() -> dict[str, Any]:
    dataset = load_dataset()
    results = [score_decision(scenario, baseline_decision(scenario)) for scenario in dataset["scenarios"]]
    category_results: dict[str, list[dict]] = defaultdict(list)
    for result in results:
        category_results[result["category"]].append(result)
    categories = [
        {
            "category": category,
            "count": len(items),
            "passed": sum(item["passed"] for item in items),
            "safety_passed": sum(item["safety_passed"] for item in items),
            "average_score": round(mean(item["score"] for item in items), 1),
        }
        for category, items in sorted(category_results.items())
    ]
    metric_averages = {
        metric: round(mean(result["metrics"][metric] / weight * 100 for result in results), 1)
        for metric, weight in METRIC_WEIGHTS.items()
    }
    violations = [
        {"scenario_id": result["scenario_id"], **violation}
        for result in results for violation in result["violations"]
    ]
    return {
        "dataset": {
            "version": dataset["version"],
            "scenario_count": len(results),
            "synthetic": True,
            "categories": len(categories),
        },
        "policy": "deterministic_single_agent_baseline",
        "summary": {
            "passed": sum(result["passed"] for result in results),
            "failed": sum(not result["passed"] for result in results),
            "safety_passed": sum(result["safety_passed"] for result in results),
            "hard_safety_violations": len(violations),
            "average_score": round(mean(result["score"] for result in results), 1),
        },
        "metric_weights": METRIC_WEIGHTS,
        "metric_averages": metric_averages,
        "categories": categories,
        "violations": violations,
        "results": results,
    }
