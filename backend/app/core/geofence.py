import math
from typing import Tuple, Optional
from ..config import settings

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance between two GPS coordinates in meters.
    """
    R = 6371000.0  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return R * c

def verify_location(
    lat: float,
    lng: float,
    accuracy: float,
    is_mock: bool,
    campus_lat: float,
    campus_lng: float,
    campus_radius_m: float
) -> Tuple[bool, Optional[str], float, int]:
    """
    Validates user GPS against security gates:
    - Mock GPS flag
    - GPS accuracy gate
    - Geofence boundary
    Returns: (is_valid, failure_code, distance_m, added_risk_score)
    """
    if is_mock:
        return False, "MOCK_LOCATION", 0.0, 0

    if accuracy > settings.MAX_GPS_ACCURACY_M:
        return False, "LOW_GPS_ACCURACY", 0.0, 0

    distance_m = haversine_distance(lat, lng, campus_lat, campus_lng)

    if distance_m > campus_radius_m:
        return False, "OUTSIDE_CAMPUS", distance_m, 0

    # Risk Scoring additions (per docs/api.md Section: Risk Scoring Calculation):
    # - +20 if GPS accuracy > 50 meters
    # - +10 if distance from campus center > 80% of allowed radius
    risk = 0
    if accuracy > 50.0:
        risk += 20
    if distance_m > (0.80 * campus_radius_m):
        risk += 10

    return True, None, distance_m, risk
