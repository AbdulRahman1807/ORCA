"""Geodesy. Degrees are never used as a unit of distance or area."""
from __future__ import annotations

import math

from ..schemas.core import BBox, haversine_km

EARTH_R_KM = 6371.0088


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return haversine_km(lat1, lon1, lat2, lon2)


def bbox_from_point_radius(lat: float, lon: float, radius_km: float) -> BBox:
    """Geodesic bounding box around a point.

    A degree of longitude shrinks with latitude, so the longitude half-width is
    divided by cos(lat). Naive degree padding is a correctness bug and is
    asserted against in the tests.
    """
    if radius_km <= 0:
        raise ValueError("radius_km must be positive")
    dlat = math.degrees(radius_km / EARTH_R_KM)
    coslat = math.cos(math.radians(lat))
    if abs(coslat) < 1e-9:                       # at the poles longitude is undefined
        dlon = 180.0
    else:
        dlon = math.degrees(radius_km / (EARTH_R_KM * coslat))
    return BBox(
        min_lat=max(-90.0, lat - dlat), max_lat=min(90.0, lat + dlat),
        min_lon=max(-180.0, lon - dlon), max_lon=min(180.0, lon + dlon),
    )


def bbox_area_km2(bbox: BBox) -> float:
    return bbox.area_km2()


def point_in_bbox(lat: float, lon: float, bbox: BBox) -> bool:
    return (bbox.min_lat <= lat <= bbox.max_lat
            and bbox.min_lon <= lon <= bbox.max_lon)


def vector_magnitude_direction(u: float, v: float, *,
                               convention: str = "towards") -> tuple[float, float]:
    """Speed and direction from vector components.

    `convention` is recorded because it is not inferable from the numbers:
    ocean currents are conventionally reported as the direction they flow
    TOWARDS, wind as the direction it blows FROM.
    """
    speed = math.hypot(u, v)
    bearing = (math.degrees(math.atan2(u, v)) + 360.0) % 360.0
    if convention == "from":
        bearing = (bearing + 180.0) % 360.0
    elif convention != "towards":
        raise ValueError("convention must be 'towards' or 'from'")
    return speed, bearing
