from __future__ import annotations

"""Optional live public-data adapters.

The demo intentionally runs from deterministic replay snapshots. These adapters
define the production seam for SREC, WFIGS, FEMA, and WSDOT without making the
MVP depend on network availability. Enable and normalize them in a later phase.
"""

import httpx

from .dataset import SOURCE_REGISTRY


class PublicDataAdapter:
    def __init__(self, timeout_seconds: float = 8.0) -> None:
        self.client = httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True)

    async def query_arcgis(self, source_id: str, params: dict) -> dict:
        source = SOURCE_REGISTRY[source_id]
        if not source["url"]:
            raise ValueError(f"{source_id} has no public endpoint")
        response = await self.client.get(f"{source['url']}/query", params={**params, "f": "geojson"})
        response.raise_for_status()
        return response.json()

    async def fetch_srec_evacuation(self, lon: float, lat: float) -> dict:
        return await self.query_arcgis("SREC", {
            "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "returnGeometry": "true",
        })

    async def fetch_wfigs(self) -> dict:
        return await self.query_arcgis("WFIGS", {
            "where": "1=1", "outFields": "*", "returnGeometry": "true", "outSR": 4326,
        })

    async def fetch_fema_shelters(self, state: str = "WA", county: str = "Spokane") -> dict:
        # FEMA's open-shelter layer is layer 0.
        url = f"{SOURCE_REGISTRY['FEMA_ESF6']['url']}/0/query"
        response = await self.client.get(url, params={
            "where": f"state='{state}' AND county_parish='{county}'",
            "outFields": "*", "returnGeometry": "true", "outSR": 4326, "f": "geojson",
        })
        response.raise_for_status()
        return response.json()

    async def fetch_wsdot_closures(self, envelope: str = "-117.75,47.50,-117.05,48.05") -> dict:
        return await self.query_arcgis("WSDOT", {
            "geometry": envelope, "geometryType": "esriGeometryEnvelope", "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "returnGeometry": "true",
        })

    async def close(self) -> None:
        await self.client.aclose()
