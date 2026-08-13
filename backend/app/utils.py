from __future__ import annotations

from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from typing import Iterable


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def active_at(record: dict, at: str, start_key: str = "valid_from", end_key: str = "valid_to") -> bool:
    target = parse_time(at)
    start = parse_time(record[start_key])
    end_value = record.get(end_key)
    return start <= target and (end_value is None or target < parse_time(end_value))


def point_in_polygon(lon: float, lat: float, geometry: dict) -> bool:
    ring = geometry["coordinates"][0]
    inside = False
    previous = len(ring) - 1
    for current, (x, y) in enumerate(ring):
        px, py = ring[previous]
        crosses = (y > lat) != (py > lat)
        if crosses and lon < (px - x) * (lat - y) / ((py - y) or 1e-12) + x:
            inside = not inside
        previous = current
    return inside


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return radius * 2 * asin(sqrt(a))


def line_near_point(start: tuple[float, float], end: tuple[float, float], point: tuple[float, float], threshold_km: float) -> bool:
    # Fast local projection suitable for the small Spokane demo area.
    sy, sx = start
    ey, ex = end
    py, px = point
    scale = cos(radians((sy + ey + py) / 3))
    ax, ay = sx * scale, sy
    bx, by = ex * scale, ey
    qx, qy = px * scale, py
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    t = 0 if denom == 0 else max(0, min(1, ((qx - ax) * dx + (qy - ay) * dy) / denom))
    nearest_lon = (ax + t * dx) / scale
    nearest_lat = ay + t * dy
    return haversine_km(nearest_lat, nearest_lon, py, px) <= threshold_km


def public_record(record: dict, keys: Iterable[str] | None = None) -> dict:
    chosen = record if keys is None else {key: record.get(key) for key in keys}
    return {key: value for key, value in chosen.items() if key not in {"person_name"}}

