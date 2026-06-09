"""Historical aircraft comparison service.

Loads `packages/historical-aircraft/database.yaml` once and provides a
similarity-based lookup that ranks reference aircraft against the current spec.

Similarity uses normalised log-space distance over a small set of geometry
and mission features so that single-engine UAVs and airliners can coexist in
the same database without distorting the metric.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from services.api.app.schemas.aircraft_spec import AircraftSpec

_DB_PATH = (
    Path(__file__).resolve().parents[4]
    / "packages"
    / "historical-aircraft"
    / "database.yaml"
)


# Feature weights — sum is informational, not enforced.
# Geometry features dominate; mission features add nuance.
_FEATURE_WEIGHTS: dict[str, float] = {
    "wingspan_m": 1.5,
    "length_m": 1.0,
    "mtow_kg": 1.5,
    "payload_kg": 1.0,
    "cruise_speed_kmh": 1.0,
    "range_km": 0.8,
    "aspect_ratio": 0.7,
}


@dataclass(frozen=True)
class HistoricalMatch:
    aircraft_id: str
    name: str
    role: str
    layout: str
    similarity: float          # 0..1, 1 == identical features
    distance: float            # weighted log-distance (lower is closer)
    deltas: dict[str, float]   # signed (current - reference) per feature
    reference: dict[str, Any]


@lru_cache(maxsize=1)
def load_database() -> list[dict[str, Any]]:
    if not _DB_PATH.exists():
        return []
    with open(_DB_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    aircraft = data.get("aircraft") or []
    if not isinstance(aircraft, list):
        return []
    return aircraft


def _scalar(value: Any, fallback: float | None = None) -> float | None:
    if value is None:
        return fallback
    raw = getattr(value, "value", value)
    if raw is None:
        return fallback
    try:
        f = float(raw)
    except (TypeError, ValueError):
        return fallback
    if f != f:  # NaN
        return fallback
    return f


def _wing_area(spec: AircraftSpec) -> float:
    span = _scalar(spec.wing.span, 0.0) or 0.0
    rc = _scalar(spec.wing.root_chord, 0.0) or 0.0
    tc = _scalar(spec.wing.tip_chord, 0.0) or 0.0
    return span * (rc + tc) / 2.0


def _aspect_ratio(spec: AircraftSpec) -> float:
    span = _scalar(spec.wing.span, 0.0) or 0.0
    area = _wing_area(spec)
    return (span * span / area) if area > 0 else 0.0


def _spec_to_features(spec: AircraftSpec) -> dict[str, float]:
    span = _scalar(spec.wing.span, 0.0) or 0.0
    length = _scalar(spec.fuselage.length, 0.0) or 0.0

    payload = _scalar(getattr(spec.mission, "payload", None), 0.0) or 0.0
    user_mtow = _scalar(getattr(spec.mission, "mtow", None))
    mtow = user_mtow if user_mtow and user_mtow > 0 else (payload / 0.15 if payload > 0 else 0.0)

    cruise = _scalar(getattr(spec.mission, "cruise_speed", None), 0.0) or 0.0
    range_km = _scalar(getattr(spec.mission, "range", None), 0.0) or 0.0
    return {
        "wingspan_m": span,
        "length_m": length,
        "mtow_kg": mtow,
        "payload_kg": payload,
        "cruise_speed_kmh": cruise,
        "range_km": range_km,
        "aspect_ratio": _aspect_ratio(spec),
    }


def _log_distance(a: float, b: float) -> float:
    """Symmetric log-space distance, robust to scale spread."""
    if a <= 0 or b <= 0:
        return 0.0  # skip when either side is missing
    return abs(math.log10(a / b))


def _compute_distance(
    current: dict[str, float], reference: dict[str, Any],
) -> tuple[float, dict[str, float], int]:
    total = 0.0
    used_weight = 0.0
    deltas: dict[str, float] = {}
    used = 0
    for feature, weight in _FEATURE_WEIGHTS.items():
        a = current.get(feature, 0.0)
        b = reference.get(feature)
        if not isinstance(b, (int, float)):
            continue
        if a <= 0 or b <= 0:
            continue
        d = _log_distance(a, float(b))
        total += weight * d
        used_weight += weight
        deltas[feature] = a - float(b)
        used += 1
    distance = total / used_weight if used_weight > 0 else float("inf")
    return distance, deltas, used


def _distance_to_similarity(distance: float) -> float:
    if not math.isfinite(distance):
        return 0.0
    # log10 ratio of 1 -> distance ~ 1.0 -> similarity ~ 0.1
    return max(0.0, math.exp(-distance * 2.3))


def find_similar(spec: AircraftSpec, top_k: int = 5) -> list[HistoricalMatch]:
    db = load_database()
    if not db:
        return []
    current = _spec_to_features(spec)
    spec_layout = spec.aircraft.layout

    matches: list[HistoricalMatch] = []
    for ref in db:
        distance, deltas, used = _compute_distance(current, ref)
        if used == 0 or not math.isfinite(distance):
            continue
        similarity = _distance_to_similarity(distance)
        # Layout match adds a small bonus (clamped to 1.0)
        if ref.get("layout") == spec_layout:
            similarity = min(1.0, similarity * 1.10)
        matches.append(HistoricalMatch(
            aircraft_id=str(ref.get("id", "")),
            name=str(ref.get("name", "")),
            role=str(ref.get("role", "")),
            layout=str(ref.get("layout", "")),
            similarity=similarity,
            distance=distance,
            deltas=deltas,
            reference=ref,
        ))

    matches.sort(key=lambda m: -m.similarity)
    return matches[:top_k]


def match_to_dict(match: HistoricalMatch) -> dict[str, Any]:
    return {
        "aircraft_id": match.aircraft_id,
        "name": match.name,
        "role": match.role,
        "layout": match.layout,
        "similarity": round(match.similarity, 4),
        "distance": round(match.distance, 4),
        "deltas": {k: round(v, 3) for k, v in match.deltas.items()},
        "reference": match.reference,
    }


def build_comparison_payload(
    spec: AircraftSpec, top_k: int = 5,
) -> dict[str, Any]:
    matches = find_similar(spec, top_k=top_k)
    return {
        "spec_features": _spec_to_features(spec),
        "matches": [match_to_dict(m) for m in matches],
        "database_size": len(load_database()),
    }
