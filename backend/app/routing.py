from __future__ import annotations

import math
import os
from typing import Any

import httpx


class OpenRouteServiceRouter:
    """Small synchronous ORS adapter with a fail-closed replay fallback upstream."""

    def __init__(self, timeout_seconds: float = 12.0) -> None:
        self.provider = os.getenv("ROUTING_PROVIDER", "replay").lower()
        self.api_key = os.getenv("ORS_API_KEY", "").strip()
        self.base_url = os.getenv("ORS_BASE_URL", "https://api.openrouteservice.org").rstrip("/")
        self.timeout_seconds = timeout_seconds

    @property
    def enabled(self) -> bool:
        return self.provider == "openrouteservice" and bool(self.api_key)

    @staticmethod
    def _avoid_polygons(closures: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not closures:
            return None
        polygons = []
        for closure in closures:
            lat = float(closure["lat"])
            lon = float(closure["lon"])
            radius_km = float(closure["radius_km"])
            lat_delta = radius_km / 111.0
            lon_delta = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.2))
            ring = []
            for index in range(17):
                angle = 2 * math.pi * index / 16
                ring.append([lon + lon_delta * math.cos(angle), lat + lat_delta * math.sin(angle)])
            polygons.append([ring])
        return {"type": "MultiPolygon", "coordinates": polygons}

    def route(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        closures: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        payload: dict[str, Any] = {
            "coordinates": [[start[1], start[0]], [end[1], end[0]]],
            "instructions": False,
        }
        avoid_polygons = self._avoid_polygons(closures)
        if avoid_polygons:
            payload["options"] = {"avoid_polygons": avoid_polygons}
        response = httpx.post(
            f"{self.base_url}/v2/directions/driving-car/geojson",
            headers={"Authorization": self.api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        feature = response.json()["features"][0]
        summary = feature["properties"]["summary"]
        return {
            "route": feature["geometry"]["coordinates"],
            "distance_km": round(summary["distance"] / 1000, 1),
            "duration_minutes": round(summary["duration"] / 60),
            "routing_provider": "openrouteservice",
            "live_route": True,
        }
