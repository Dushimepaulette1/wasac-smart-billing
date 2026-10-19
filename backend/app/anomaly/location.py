"""Was the meter photo taken at the meter?

The phone sends where it was when the photo was taken (with the accuracy the
phone reports) and whether the photo came from the camera or was uploaded
from the gallery. That is compared with the meter's location on file:

    ok           within LOCATION_MAX_M (plus the phone's own accuracy) of the meter
    not_checked  the meter has no location on file, so nothing to compare with
    far          further away than that
    no_location  the phone sent no location (permission refused, or no fix)
    imprecise    the phone's position is too rough to tell (accuracy > LOCATION_MAX_ACCURACY_M)
    upload       the photo was chosen from the gallery, not taken now

Every outcome but ok and not_checked holds the reading for an officer to check
(anomaly type LOCATION_CHECK). Readings are never rejected for this; an
officer can accept them. Location is evidence, not proof: it can be faked by
a determined person, so it decides who gets a second look, nothing more.
"""
import math
import os
from dataclasses import dataclass
from typing import Optional


NEEDS_REVIEW = {"far", "no_location", "imprecise", "upload"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


@dataclass
class PhotoEvidence:
    photo_source: str = "camera"
    lat: Optional[float] = None
    lng: Optional[float] = None
    accuracy_m: Optional[float] = None


@dataclass
class LocationCheck:
    outcome: str
    distance_m: Optional[float] = None

    @property
    def needs_review(self) -> bool:
        return self.outcome in NEEDS_REVIEW

    def features(self, evidence: PhotoEvidence) -> dict:
        return {
            "location_check": self.outcome,
            "distance_m": None if self.distance_m is None else round(self.distance_m),
            "accuracy_m": None if evidence.accuracy_m is None else round(evidence.accuracy_m),
            "photo_source": evidence.photo_source,
        }


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres (haversine)."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def check_location(meter_lat: Optional[float], meter_lng: Optional[float], evidence: PhotoEvidence) -> LocationCheck:
    max_m = _env_float("LOCATION_MAX_M", 150.0)
    max_accuracy = _env_float("LOCATION_MAX_ACCURACY_M", 500.0)
    has_fix = evidence.lat is not None and evidence.lng is not None
    distance = (
        distance_m(meter_lat, meter_lng, evidence.lat, evidence.lng)
        if has_fix and meter_lat is not None and meter_lng is not None
        else None
    )
    if evidence.photo_source == "upload":
        return LocationCheck("upload", distance)
    if meter_lat is None or meter_lng is None:
        return LocationCheck("not_checked")
    if not has_fix:
        return LocationCheck("no_location")
    accuracy = evidence.accuracy_m if evidence.accuracy_m is not None else 0.0
    if accuracy > max_accuracy:
        return LocationCheck("imprecise", distance)
    # The phone may be off by its accuracy; only call it far when it is far even allowing for that.
    return LocationCheck("far" if distance - accuracy > max_m else "ok", distance)
