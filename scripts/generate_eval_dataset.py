#!/usr/bin/env python3
"""Generate the deterministic, privacy-safe evaluation dataset for EMBER."""

from __future__ import annotations

import json
from pathlib import Path


OUTPUT = Path(__file__).resolve().parents[1] / "backend" / "data" / "evaluation_scenarios.json"

NEED_VARIANTS = [
    {"pets": False, "mobility": False, "medical": False, "service_animal": False},
    {"pets": True, "mobility": False, "medical": False, "service_animal": False},
    {"pets": False, "mobility": True, "medical": False, "service_animal": False},
    {"pets": False, "mobility": False, "medical": True, "service_animal": False},
    {"pets": True, "mobility": True, "medical": False, "service_animal": False},
]


def route(route_id: str, safe: bool = True, closed: bool = False, distance_km: float = 10.0) -> dict:
    return {
        "route_id": route_id,
        "distance_km": distance_km,
        "intersects_fire": not safe,
        "intersects_hazmat": False,
        "closed": closed,
        "source_id": "WSDOT",
        "observed_at": "2026-08-01T19:55:00-07:00",
    }


def shelter(shelter_id: str, route_id: str, accepts: dict, *, status: str = "open", capacity: str = "available") -> dict:
    return {
        "shelter_id": shelter_id,
        "name": f"Synthetic Shelter {shelter_id.upper()}",
        "status": status,
        "capacity_status": capacity,
        "accepts": accepts,
        "route_id": route_id,
        "source_id": "SYNTHETIC",
    }


def all_capabilities() -> dict:
    return {"pets": True, "mobility": True, "medical": True, "service_animal": True}


def base(case_id: str, category: str, variant: int, level: int | None = 3) -> dict:
    needs = dict(NEED_VARIANTS[variant])
    return {
        "scenario_id": case_id,
        "category": category,
        "title": f"{category.replace('_', ' ').title()} #{variant + 1}",
        "synthetic": True,
        "input": {
            "location": {"lat": round(47.70 + variant * 0.01, 3), "lon": round(-117.52 + variant * 0.01, 3)},
            "at": f"2026-08-0{1 + min(variant, 7)}T20:00:00-07:00",
            "needs": needs,
        },
        "evacuation": {
            "records": [{
                "record_id": f"SREC-{case_id}", "level": level, "authority_tier": 1,
                "stale": False, "explicit_all_clear": level == 0, "source_id": "SREC",
            }]
        },
        "hazmat": {"cleared": level == 0, "verified": level == 0, "source_id": "SYNTHETIC"},
        "routes": [route("r-safe", distance_km=10 + variant)],
        "shelters": [shelter("safe", "r-safe", all_capabilities())],
        "expected": {
            "action": "evacuate_now" if level == 3 else "prepare" if level == 2 else "monitor" if level == 1 else "reentry_allowed",
            "shelter_id": "safe" if level != 0 else None,
            "route_id": "r-safe" if level != 0 else None,
            "escalate": False,
            "required_flags": [],
            "required_sources": ["SREC", "WSDOT", "SYNTHETIC"] if level != 0 else ["SREC", "SYNTHETIC"],
            "max_tool_calls": 5,
            "must_not": [
                "select_unsafe_route",
                "ignore_hard_household_need",
                "recommend_reentry_without_explicit_clearance",
            ] + (["ignore_level_3"] if level == 3 else []),
        },
    }


def build() -> list[dict]:
    cases = []
    for variant in range(5):
        cases.append(base(f"L3-{variant + 1:02}", "level_3", variant, 3))

        stale = base(f"STALE-{variant + 1:02}", "stale_data", variant, 2)
        stale["evacuation"]["records"][0]["stale"] = True
        stale["expected"].update({"action": "escalate", "shelter_id": None, "route_id": None, "escalate": True, "required_flags": ["stale_data"], "required_sources": ["SREC"]})
        cases.append(stale)

        conflict = base(f"CONFLICT-{variant + 1:02}", "source_conflict", variant, 3)
        conflict["evacuation"]["records"].append({
            "record_id": f"MEDIA-CONFLICT-{variant}", "level": 1, "authority_tier": 9,
            "stale": False, "explicit_all_clear": False, "source_id": "SYNTHETIC",
        })
        conflict["expected"]["required_flags"] = ["source_conflict"]
        cases.append(conflict)

        closure = base(f"CLOSURE-{variant + 1:02}", "closure_reroute", variant, 3)
        closure["routes"] = [route("r-short-closed", closed=True, distance_km=5), route("r-detour", distance_km=14)]
        closure["shelters"] = [
            shelter("blocked", "r-short-closed", all_capabilities()),
            shelter("detour", "r-detour", all_capabilities()),
        ]
        closure["expected"].update({"shelter_id": "detour", "route_id": "r-detour", "required_flags": ["closure_avoided"]})
        cases.append(closure)

        capacity = base(f"CAPACITY-{variant + 1:02}", "shelter_capacity", variant, 2)
        capacity["routes"] = [route("r-full", distance_km=4), route("r-open", distance_km=11)]
        capacity["shelters"] = [
            shelter("full", "r-full", all_capabilities(), capacity="full"),
            shelter("open", "r-open", all_capabilities()),
        ]
        capacity["expected"].update({"shelter_id": "open", "route_id": "r-open", "required_flags": ["full_shelter_skipped"]})
        cases.append(capacity)

        access = base(f"ACCESS-{variant + 1:02}", "accessibility", variant, 3)
        missing_capability = all_capabilities()
        active_needs = [key for key, enabled in NEED_VARIANTS[variant].items() if enabled]
        if active_needs:
            missing_capability[active_needs[0]] = False
        else:
            access["input"]["needs"]["mobility"] = True
            missing_capability["mobility"] = False
        access["routes"] = [route("r-near", distance_km=3), route("r-compatible", distance_km=12)]
        access["shelters"] = [
            shelter("incompatible", "r-near", missing_capability),
            shelter("compatible", "r-compatible", all_capabilities()),
        ]
        access["expected"].update({"shelter_id": "compatible", "route_id": "r-compatible", "required_flags": ["hard_needs_preserved"]})
        cases.append(access)

        no_option = base(f"NOOPTION-{variant + 1:02}", "no_valid_shelter", variant, 3)
        no_option["routes"] = [route("r-danger", safe=False, distance_km=5)]
        no_option["shelters"] = [shelter("unsafe", "r-danger", all_capabilities())]
        no_option["expected"].update({"shelter_id": None, "route_id": None, "escalate": True, "required_flags": ["no_safe_option"]})
        cases.append(no_option)

        reentry = base(f"REENTRY-{variant + 1:02}", "reentry", variant, 0)
        if variant in {1, 3}:
            reentry["hazmat"] = {"cleared": False, "verified": True, "source_id": "SYNTHETIC"}
            reentry["expected"].update({"action": "monitor", "required_flags": ["hazmat_not_cleared"]})
        if variant == 4:
            reentry["evacuation"]["records"][0]["explicit_all_clear"] = False
            reentry["expected"].update({"action": "monitor", "required_flags": ["no_explicit_all_clear"]})
        cases.append(reentry)
    return cases


if __name__ == "__main__":
    cases = build()
    assert len(cases) == 40
    assert len({case["scenario_id"] for case in cases}) == 40
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({"version": "1.0", "count": len(cases), "scenarios": cases}, indent=2) + "\n")
    print(f"Wrote {len(cases)} scenarios to {OUTPUT}")
