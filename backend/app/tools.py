from __future__ import annotations

import re
import threading
import uuid
from datetime import timedelta
from typing import Any

from .dataset import (
    EVACUATION_SNAPSHOTS,
    HAZMAT,
    INCIDENT_SNAPSHOTS,
    ROAD_CLOSURES,
    SHELTERS,
    SOURCE_REGISTRY,
    initial_store,
)
from .models import Needs
from .routing import OpenRouteServiceRouter
from .utils import active_at, haversine_km, line_near_point, parse_time, point_in_polygon


class AgentTools:
    """The seven callable tools from the framework, backed by replay data.

    The public APIs are represented by source metadata and can be swapped in through
    adapters later. Personal data is intentionally synthetic and held in memory.
    """

    def __init__(self, router: OpenRouteServiceRouter | None = None) -> None:
        self._sessions: dict[str, dict] = {}
        self._lock = threading.Lock()
        self.router = router or OpenRouteServiceRouter()

    def _store(self, session_id: str) -> dict:
        with self._lock:
            return self._sessions.setdefault(session_id, initial_store())

    @staticmethod
    def _provenance(record: dict, at: str) -> dict:
        source = SOURCE_REGISTRY[record["source_id"]]
        age = parse_time(at) - parse_time(record["observed_at"])
        ttl = timedelta(minutes=source["ttl_minutes"])
        # Replay records are snapshots, not claims that an old feed is currently live.
        stale = age > ttl and source["class"] != "synthetic"
        return {
            "source_id": record["source_id"],
            "source_name": source["name"],
            "source_class": source["class"],
            "source_url": source["url"],
            "observed_at": record["observed_at"],
            "as_of": at,
            "stale": stale,
        }

    def get_evacuation_status(self, address: str, lat: float, lon: float, at: str) -> dict[str, Any]:
        matches = [
            row for row in EVACUATION_SNAPSHOTS
            if active_at(row, at) and point_in_polygon(lon, lat, row["geometry"])
        ]
        if not matches:
            return {
                "level": None,
                "zone_name": None,
                "official_message": "No active polygon was found. Absence is not an all-clear.",
                "all_clear": False,
                "conflicts": [],
                "provenance": None,
            }
        ranked = sorted(
            matches,
            key=lambda row: (SOURCE_REGISTRY[row["source_id"]]["authority_tier"], -row["level"]),
        )
        winner = ranked[0]
        conflicts = [
            {
                "source_id": row["source_id"],
                "reported_level": row["level"],
                "resolution": "Official/higher-authority and conservative level selected.",
            }
            for row in matches if row["level"] != winner["level"]
        ]
        return {
            "level": winner["level"],
            "zone_name": winner["zone_name"],
            "status": winner["status"],
            "official_message": winner["message"],
            "all_clear": winner["status"].lower() == "all clear",
            "conflicts": conflicts,
            "provenance": self._provenance(winner, at),
            "geometry": winner["geometry"],
            "address": address,
        }

    def get_active_incidents(self, lat: float, lon: float, radius_km: float, at: str) -> list[dict[str, Any]]:
        eligible = [row for row in INCIDENT_SNAPSHOTS if parse_time(row["observed_at"]) <= parse_time(at)]
        latest_by_event: dict[str, dict] = {}
        for row in eligible:
            current = latest_by_event.get(row["event_id"])
            if current is None or parse_time(row["observed_at"]) > parse_time(current["observed_at"]):
                latest_by_event[row["event_id"]] = row
        incidents = []
        for row in latest_by_event.values():
            distance = haversine_km(lat, lon, row["lat"], row["lon"])
            if distance <= radius_km:
                incidents.append({
                    "event_id": row["event_id"],
                    "name": row["name"],
                    "distance_km": round(distance, 1),
                    "acres": row["acres"],
                    "containment_pct": row["containment_pct"],
                    "structures_lost": row["structures_lost"],
                    "damage_count_note": (
                        "Not available in this replay snapshot."
                        if row["structures_lost"] is None
                        else "Dated NIFC snapshot; operational figures may be revised."
                    ),
                    "geometry": row["geometry"],
                    "provenance": self._provenance(row, at),
                })
        return sorted(incidents, key=lambda item: item["distance_km"])

    def _active_closures(self, at: str) -> list[dict]:
        return [row for row in ROAD_CLOSURES if active_at(row, at, "active_from", "active_to")]

    def find_shelters(self, lat: float, lon: float, needs: Needs, at: str) -> list[dict[str, Any]]:
        results = []
        closures = self._active_closures(at)
        need_map = needs.model_dump()
        hard_needs = [key for key, value in need_map.items() if value]
        for shelter in SHELTERS:
            unmet = [key for key in hard_needs if not shelter["accepts"].get(key, False)]
            if shelter["status"] != "open" or shelter["capacity_status"] == "full" or unmet:
                continue
            blocking = [
                closure for closure in closures
                if line_near_point(
                    (lat, lon), (shelter["lat"], shelter["lon"]),
                    (closure["lat"], closure["lon"]), closure["radius_km"],
                )
            ]
            straight = haversine_km(lat, lon, shelter["lat"], shelter["lon"])
            # The MVP returns a demonstrable safe-route corridor, not turn-by-turn navigation.
            detour_factor = 1.45 if blocking else 1.18
            route_data = None
            route_error = None
            try:
                route_data = self.router.route(
                    (lat, lon), (shelter["lat"], shelter["lon"]), closures,
                )
            except Exception as exc:
                route_error = type(exc).__name__
            result = {
                "shelter_id": shelter["shelter_id"],
                "name": shelter["name"],
                "address": shelter["address"],
                "lat": shelter["lat"],
                "lon": shelter["lon"],
                "distance_km": round(straight * detour_factor, 1),
                "duration_minutes": None,
                "capacity_status": shelter["capacity_status"],
                "accepts": shelter["accepts"],
                "unmet_needs": [],
                "route_status": "detour_required" if blocking else "candidate_clear",
                "route_warning": (
                    "Candidate corridor intersects a reported closure; use the displayed detour and verify official navigation."
                    if blocking else "No known closure intersects the candidate corridor in the replay dataset."
                ),
                "closures_avoided": [item["name"] for item in blocking],
                "route": [[lon, lat], [shelter["lon"], shelter["lat"]]],
                "routing_provider": "replay_fallback",
                "live_route": False,
                "provenance": self._provenance(shelter, at),
                "capabilities_are_synthetic": True,
            }
            if route_data:
                result.update(route_data)
                result["route_warning"] = (
                    "Live ORS candidate route generated while avoiding active closure buffers; verify official road status before departure."
                )
            elif route_error:
                result["route_fallback_reason"] = route_error
            results.append(result)
        return sorted(results, key=lambda item: (item["route_status"] != "candidate_clear", item["distance_km"]))

    def check_hazmat_clearance(self, address: str, zone_name: str | None, at: str) -> dict[str, Any]:
        matches = [row for row in HAZMAT if row["zone_name"] == zone_name and active_at(row, at)]
        if not matches:
            return {
                "cleared": False,
                "verified": False,
                "notes": "No explicit hazmat all-clear was found. Do not infer clearance from missing data.",
                "provenance": None,
                "address": address,
            }
        row = matches[-1]
        return {
            "cleared": row["cleared"],
            "verified": True,
            "notes": row["notes"],
            "provenance": self._provenance(row, at),
            "address": address,
        }

    def file_missing_person(
        self,
        session_id: str,
        name: str,
        last_known_location: str,
        contact: str,
        consent: bool,
    ) -> dict[str, Any]:
        if not consent:
            return {"status": "blocked", "reason": "Explicit consent is required for the synthetic demo workflow."}
        clean_name = re.sub(r"[^A-Za-zÀ-ž' -]", "", name).strip()[:80]
        if not clean_name:
            return {"status": "blocked", "reason": "A valid name is required."}
        report = {
            "report_id": f"SYN-{uuid.uuid4().hex[:8].upper()}",
            "name": clean_name,
            "last_known_location": last_known_location[:160],
            "contact": contact[:120],
            "source_id": "SYNTHETIC",
            "status": "open",
        }
        self._store(session_id)["missing_reports"].append(report)
        return {
            "status": "filed",
            "report_id": report["report_id"],
            "source_id": "SYNTHETIC",
            "privacy": "Demo only. Stored in memory and never sent to authorities.",
        }

    def search_missing_reports(self, session_id: str, name: str, consent: bool) -> list[dict[str, Any]]:
        if not consent:
            return [{"status": "blocked", "reason": "Explicit consent is required."}]
        normalized = name.casefold().strip()
        matches = []
        store = self._store(session_id)
        shelter_names = {row["shelter_id"]: row["name"] for row in SHELTERS}
        for checkin in store["checkins"]:
            confidence = 0.99 if checkin["person_name"].casefold() == normalized else 0.0
            if confidence:
                matches.append({
                    "match_confidence": confidence,
                    "shelter": shelter_names[checkin["shelter_id"]],
                    "checked_in_at": checkin["checked_in_at"],
                    "status": checkin["status"],
                    "source_id": "SYNTHETIC",
                    "source_class": "synthetic",
                    "privacy": "Synthetic demo match; not a real person or official report.",
                })
        return matches

    def send_notification(self, session_id: str, contact: str, message: str) -> dict[str, Any]:
        notification = {
            "notification_id": f"MSG-{uuid.uuid4().hex[:8].upper()}",
            "channel": "demo",
            "contact_masked": self._mask_contact(contact),
            "message": message,
            "status": "simulated",
            "source_id": "SYNTHETIC",
        }
        self._store(session_id)["notifications"].append(notification)
        return notification

    @staticmethod
    def _mask_contact(contact: str) -> str:
        if "@" in contact:
            head, tail = contact.split("@", 1)
            return f"{head[:2]}***@{tail}"
        digits = re.sub(r"\D", "", contact)
        return f"***{digits[-4:]}" if digits else "hidden"
