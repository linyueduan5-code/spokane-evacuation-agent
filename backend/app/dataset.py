from __future__ import annotations

from copy import deepcopy


SOURCE_REGISTRY = {
    "SREC": {
        "name": "Spokane Regional Emergency Communications evacuation areas",
        "class": "official",
        "authority_tier": 1,
        "url": "https://services3.arcgis.com/9UdSzuxhN4jGcI9p/arcgis/rest/services/Evacuation_Areas_Spokane_County_Share_View/FeatureServer/0",
        "ttl_minutes": 10,
    },
    "WFIGS": {
        "name": "NIFC WFIGS current fire perimeters",
        "class": "official",
        "authority_tier": 1,
        "url": "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters_Current/FeatureServer/0",
        "ttl_minutes": 30,
    },
    "NIFC_IMSR": {
        "name": "NIFC Incident Management Situation Report, 10 Aug 2026",
        "class": "official",
        "authority_tier": 1,
        "url": "https://www.nifc.gov/fire-information",
        "ttl_minutes": 1440,
    },
    "FEMA_ESF6": {
        "name": "FEMA National Shelter System ESF #6",
        "class": "official",
        "authority_tier": 1,
        "url": "https://gis.fema.gov/arcgis/rest/services/NSS/FEMA_NSS/FeatureServer",
        "ttl_minutes": 60,
    },
    "WSDOT": {
        "name": "WSDOT road alerts",
        "class": "official",
        "authority_tier": 1,
        "url": "https://data.wsdot.wa.gov/arcgis/rest/services/TravelInformation/TravelInfoRoadAlerts/FeatureServer/2",
        "ttl_minutes": 15,
    },
    "SYNTHETIC": {
        "name": "Hackathon synthetic replay data",
        "class": "synthetic",
        "authority_tier": 9,
        "url": None,
        "ttl_minutes": 10080,
    },
}


def rectangle(west: float, south: float, east: float, north: float) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
    }


EVACUATION_SNAPSHOTS = [
    {
        "record_id": "srec-rifle-aug01",
        "event_id": "old-trails",
        "zone_name": "Old Trails - Rifle Club",
        "level": 3,
        "status": "remains",
        "message": "GO NOW. Follow official evacuation instructions.",
        "valid_from": "2026-08-01T18:00:00-07:00",
        "valid_to": "2026-08-06T09:00:00-07:00",
        "observed_at": "2026-08-01T19:58:00-07:00",
        "source_id": "SREC",
        "geometry": rectangle(-117.575, 47.700, -117.455, 47.815),
    },
    {
        "record_id": "derived-rifle-aug01-conflict",
        "event_id": "old-trails",
        "zone_name": "Old Trails - media estimate",
        "level": 2,
        "status": "reported",
        "message": "Secondary replay estimate.",
        "valid_from": "2026-08-01T19:00:00-07:00",
        "valid_to": "2026-08-01T22:00:00-07:00",
        "observed_at": "2026-08-01T19:40:00-07:00",
        "source_id": "SYNTHETIC",
        "geometry": rectangle(-117.575, 47.700, -117.455, 47.815),
    },
    {
        "record_id": "srec-rifle-aug06",
        "event_id": "old-trails",
        "zone_name": "Old Trails - Rifle Club",
        "level": 2,
        "status": "downgraded",
        "message": "SET. Conditions remain hazardous; be ready to leave.",
        "valid_from": "2026-08-06T09:00:00-07:00",
        "valid_to": "2026-08-08T18:00:00-07:00",
        "observed_at": "2026-08-06T09:02:00-07:00",
        "source_id": "SREC",
        "geometry": rectangle(-117.575, 47.700, -117.455, 47.815),
    },
    {
        "record_id": "srec-rifle-aug08",
        "event_id": "old-trails",
        "zone_name": "Old Trails - Rifle Club",
        "level": 1,
        "status": "downgraded",
        "message": "READY. Remain alert. This is not an all-clear.",
        "valid_from": "2026-08-08T18:00:00-07:00",
        "valid_to": None,
        "observed_at": "2026-08-08T18:03:00-07:00",
        "source_id": "SREC",
        "geometry": rectangle(-117.575, 47.700, -117.455, 47.815),
    },
]

INCIDENT_SNAPSHOTS = [
    {
        "event_id": "old-trails", "name": "Old Trails", "lat": 47.709, "lon": -117.566,
        "acres": 1100, "containment_pct": 0, "structures_lost": None,
        "observed_at": "2026-08-01T19:50:00-07:00", "source_id": "SYNTHETIC",
        "geometry": rectangle(-117.575, 47.698, -117.545, 47.720),
    },
    {
        "event_id": "autumn-lane", "name": "Autumn Lane", "lat": 47.790, "lon": -117.520,
        "acres": 1500, "containment_pct": 0, "structures_lost": None,
        "observed_at": "2026-08-01T19:50:00-07:00", "source_id": "SYNTHETIC",
        "geometry": rectangle(-117.535, 47.776, -117.505, 47.804),
    },
    {
        "event_id": "fairview", "name": "Fairview", "lat": 47.735, "lon": -117.380,
        "acres": 400, "containment_pct": 0, "structures_lost": None,
        "observed_at": "2026-08-01T19:50:00-07:00", "source_id": "SYNTHETIC",
        "geometry": rectangle(-117.393, 47.725, -117.367, 47.746),
    },
    {
        "event_id": "old-trails", "name": "Old Trails", "lat": 47.709, "lon": -117.566,
        "acres": 3176, "containment_pct": 53, "structures_lost": 569,
        "observed_at": "2026-08-10T08:00:00-07:00", "source_id": "NIFC_IMSR",
        "geometry": rectangle(-117.590, 47.690, -117.525, 47.735),
    },
    {
        "event_id": "autumn-lane", "name": "Autumn Lane", "lat": 47.790, "lon": -117.520,
        "acres": 5776, "containment_pct": 73, "structures_lost": 149,
        "observed_at": "2026-08-10T08:00:00-07:00", "source_id": "NIFC_IMSR",
        "geometry": rectangle(-117.552, 47.765, -117.485, 47.825),
    },
    {
        "event_id": "fairview", "name": "Fairview", "lat": 47.735, "lon": -117.380,
        "acres": 992, "containment_pct": 53, "structures_lost": 56,
        "observed_at": "2026-08-10T08:00:00-07:00", "source_id": "NIFC_IMSR",
        "geometry": rectangle(-117.405, 47.718, -117.350, 47.755),
    },
]

SHELTERS = [
    {
        "shelter_id": "s1", "name": "Spokane Convention Center", "address": "334 W Spokane Falls Blvd",
        "lat": 47.6608, "lon": -117.4177, "status": "open", "capacity_status": "available",
        "accepts": {"pets": True, "mobility": True, "medical": False, "service_animal": True},
        "observed_at": "2026-08-01T19:45:00-07:00", "source_id": "FEMA_ESF6",
        "capability_source_id": "SYNTHETIC",
    },
    {
        "shelter_id": "s2", "name": "Spokane Fair & Expo Center", "address": "404 N Havana St",
        "lat": 47.6615, "lon": -117.3490, "status": "open", "capacity_status": "limited",
        "accepts": {"pets": True, "mobility": True, "medical": True, "service_animal": True},
        "observed_at": "2026-08-01T19:50:00-07:00", "source_id": "FEMA_ESF6",
        "capability_source_id": "SYNTHETIC",
    },
    {
        "shelter_id": "s3", "name": "North Spokane RV Campground", "address": "10904 N Newport Hwy",
        "lat": 47.7587, "lon": -117.4044, "status": "open", "capacity_status": "available",
        "accepts": {"pets": True, "mobility": False, "medical": False, "service_animal": True},
        "observed_at": "2026-08-01T19:42:00-07:00", "source_id": "FEMA_ESF6",
        "capability_source_id": "SYNTHETIC",
    },
]

ROAD_CLOSURES = [
    {
        "closure_id": "c1", "name": "W Trails Rd closure", "lat": 47.728, "lon": -117.530,
        "radius_km": 1.2, "active_from": "2026-08-01T16:00:00-07:00", "active_to": "2026-08-08T12:00:00-07:00",
        "observed_at": "2026-08-01T19:55:00-07:00", "source_id": "WSDOT",
    },
    {
        "closure_id": "c2", "name": "Synthetic demo closure on downtown corridor", "lat": 47.707, "lon": -117.465,
        "radius_km": 0.8, "active_from": "2026-08-01T19:00:00-07:00", "active_to": "2026-08-02T12:00:00-07:00",
        "observed_at": "2026-08-01T19:52:00-07:00", "source_id": "SYNTHETIC",
    },
]

HAZMAT = [
    {
        "zone_name": "Old Trails - Rifle Club", "cleared": False,
        "valid_from": "2026-08-06T09:00:00-07:00", "valid_to": "2026-08-09T20:00:00-07:00",
        "observed_at": "2026-08-07T08:00:00-07:00", "source_id": "SYNTHETIC",
        "notes": "Synthetic replay: hazardous-material crews remain active; no verified all-clear.",
    }
]

SYNTHETIC_CHECKINS = [
    {
        "person_name": "Avery Chen", "shelter_id": "s1", "checked_in_at": "2026-08-01T22:15:00-07:00",
        "status": "safe", "source_id": "SYNTHETIC",
    }
]


def initial_store() -> dict:
    return {
        "missing_reports": [],
        "notifications": [],
        "checkins": deepcopy(SYNTHETIC_CHECKINS),
    }
