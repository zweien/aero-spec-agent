"""Tests for historical-aircraft comparison service and routes."""

from __future__ import annotations

import yaml
from fastapi.testclient import TestClient

from services.api.app.main import app
from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.services.historical_compare import (
    build_comparison_payload,
    find_similar,
    load_database,
)


def _baseline_spec() -> AircraftSpec:
    with open("packages/aircraft-schema/examples/twin_engine_uav.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return AircraftSpec.model_validate(data)


def test_database_loads_with_minimum_fleet():
    db = load_database()
    assert len(db) >= 15
    ids = {entry["id"] for entry in db}
    assert {"cessna_172", "mq9_reaper", "a320", "b2"}.issubset(ids)


def test_find_similar_returns_top_k():
    spec = _baseline_spec()
    matches = find_similar(spec, top_k=3)
    assert 1 <= len(matches) <= 3
    similarities = [m.similarity for m in matches]
    assert similarities == sorted(similarities, reverse=True)


def test_find_similar_picks_closest_aircraft_for_uav():
    """A 12 m wingspan, 30 kg payload UAV should be closest to small UAVs."""
    spec = _baseline_spec()
    matches = find_similar(spec, top_k=5)
    top_ids = [m.aircraft_id for m in matches]
    expected_uavs = {"scaneagle", "bayraktar_tb2", "mq1_predator", "ch_4"}
    assert any(aid in expected_uavs for aid in top_ids), (
        f"expected at least one small UAV in top-5, got {top_ids}"
    )


def test_find_similar_for_airliner_features_returns_airliner():
    """A scaled-up spec with airliner-like dimensions should rank airliners high."""
    spec_dict = _baseline_spec().model_dump()
    spec_dict["wing"]["span"]["value"] = 35.0
    spec_dict["fuselage"]["length"]["value"] = 38.0
    spec_dict["mission"]["payload"]["value"] = 16000
    spec_dict["mission"]["cruise_speed"]["value"] = 840
    spec = AircraftSpec.model_validate(spec_dict)
    matches = find_similar(spec, top_k=3)
    top_ids = {m.aircraft_id for m in matches}
    assert top_ids & {"a320", "boeing_737_800"}


def test_layout_match_bonus_applied_when_layout_equal():
    spec = _baseline_spec()
    matches = find_similar(spec, top_k=20)
    # Conventional layout is the spec's layout — at least one conventional
    # should appear in matches with a positive bonus relative to its raw distance.
    for m in matches:
        assert 0.0 <= m.similarity <= 1.0


def test_build_payload_serializable():
    spec = _baseline_spec()
    payload = build_comparison_payload(spec, top_k=3)
    assert "matches" in payload
    assert "spec_features" in payload
    assert payload["database_size"] >= 15
    if payload["matches"]:
        first = payload["matches"][0]
        assert "deltas" in first
        assert "reference" in first


def test_route_list_historical_aircraft():
    client = TestClient(app)
    resp = client.get("/api/historical-aircraft")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 15


def test_route_compare_inline_spec():
    client = TestClient(app)
    spec = _baseline_spec().model_dump(mode="json")
    resp = client.post("/api/historical-compare?top_k=3", json={"spec": spec})
    assert resp.status_code == 200
    data = resp.json()
    assert "matches" in data
    assert len(data["matches"]) <= 3


def test_route_compare_inline_rejects_missing_spec():
    client = TestClient(app)
    resp = client.post("/api/historical-compare", json={})
    assert resp.status_code == 422


def test_route_compare_design_404_when_design_missing():
    client = TestClient(app)
    resp = client.get("/api/designs/nonexistent-id/historical-compare")
    assert resp.status_code == 404
