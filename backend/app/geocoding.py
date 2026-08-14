from __future__ import annotations

import os
from functools import lru_cache

import httpx


class MapboxGeocoder:
    """Temporary geocoding adapter; results are cached only in process memory."""

    def __init__(self, timeout_seconds: float = 8.0) -> None:
        self.access_token = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
        self.timeout_seconds = timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self.access_token)

    @lru_cache(maxsize=256)
    def search(self, query: str) -> tuple[dict, ...]:
        clean_query = " ".join(query.split())[:120]
        if len(clean_query) < 3 or not self.enabled:
            return ()
        response = httpx.get(
            "https://api.mapbox.com/search/geocode/v6/forward",
            params={
                "q": clean_query,
                "access_token": self.access_token,
                "country": "us",
                "proximity": "-117.426,47.658",
                "limit": 5,
                "language": "en",
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        results = []
        for feature in response.json().get("features", []):
            properties = feature.get("properties", {})
            coordinates = feature.get("geometry", {}).get("coordinates", [])
            if len(coordinates) < 2:
                continue
            results.append({
                "id": feature.get("id"),
                "label": properties.get("full_address") or properties.get("name") or feature.get("name"),
                "lat": coordinates[1],
                "lon": coordinates[0],
                "feature_type": properties.get("feature_type"),
            })
        return tuple(results)
