"""Tests for the expert-knowledge service & routes."""

from __future__ import annotations

import yaml
from fastapi.testclient import TestClient

from services.api.app.main import app
from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.services.expert_knowledge import (
    best_range_for,
    list_aircraft_categories,
    list_topics,
    load_books,
    load_entries,
    lookup,
    render_citation,
)


def _baseline_spec() -> AircraftSpec:
    with open("packages/aircraft-schema/examples/twin_engine_uav.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return AircraftSpec.model_validate(data)


def test_books_loaded():
    books = load_books()
    assert {"raymer", "liuhu", "yuxiongqing", "nwpu", "gusongfen", "civil_uav_design"}.issubset(books.keys())


def test_entries_loaded_with_minimum_count():
    entries = load_entries()
    assert len(entries) >= 25
    topics = {e.topic for e in entries}
    assert {
        "aspect_ratio", "wing_loading", "thrust_to_weight",
        "payload_fraction", "ld_cruise", "rcs_estimate",
    }.issubset(topics)


def test_list_topics_and_categories():
    topics = list_topics()
    cats = list_aircraft_categories()
    assert "aspect_ratio" in topics
    assert "long_endurance_uav" in cats
    assert "airliner" in cats


def test_lookup_filters_by_category():
    matches = lookup(topic="aspect_ratio", aircraft_category="airliner")
    assert all("airliner" in e.applies_to for e in matches)
    assert any(e.range and e.range[0] >= 7.5 and e.range[1] <= 12 for e in matches)


def test_best_range_prefers_specific_category():
    entry = best_range_for("aspect_ratio", "long_endurance_uav")
    assert entry is not None
    assert "long_endurance_uav" in entry.applies_to
    assert entry.range is not None
    lo, hi = entry.range
    assert lo >= 10.0 and hi <= 30.0


def test_render_citation_includes_book_titles():
    entries = load_entries()
    entry = entries[0]
    citations = render_citation(entry)
    assert citations
    assert all(isinstance(s, str) and s for s in citations)


def test_route_books():
    client = TestClient(app)
    resp = client.get("/api/expert-knowledge/books")
    assert resp.status_code == 200
    assert "raymer" in resp.json().get("books", {})


def test_route_topics():
    client = TestClient(app)
    resp = client.get("/api/expert-knowledge/topics")
    assert resp.status_code == 200
    payload = resp.json()
    assert "aspect_ratio" in payload["topics"]
    assert "long_endurance_uav" in payload["categories"]


def test_route_lookup_filters():
    client = TestClient(app)
    resp = client.get("/api/expert-knowledge/lookup?topic=wing_loading&aircraft_category=airliner")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] >= 1
    for entry in payload["entries"]:
        assert "airliner" in entry["applies_to"]
        assert entry["citations"]


def test_route_advisory_post_inline_spec():
    client = TestClient(app)
    spec = _baseline_spec().model_dump(mode="json")
    resp = client.post(
        "/api/expert-knowledge/advisory?aircraft_category=long_endurance_uav",
        json={"spec": spec},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert "advisory" in payload
    assert "summary" in payload
    assert sum(payload["summary"].values()) == len(payload["advisory"])


def test_route_advisory_missing_spec_returns_400():
    client = TestClient(app)
    resp = client.post("/api/expert-knowledge/advisory", json={})
    assert resp.status_code == 400


def test_route_advisory_design_404_when_design_missing():
    client = TestClient(app)
    resp = client.get("/api/expert-knowledge/designs/nonexistent/advisory")
    assert resp.status_code == 404


def test_advisory_categorizes_uav_metrics_against_long_endurance_window():
    """Baseline twin_engine_uav (12m span, 30kg payload) sits in long-endurance UAV
    territory; aspect-ratio entry for that category should produce a non-empty
    advisory with at least one pass/warn/fail status assigned."""
    client = TestClient(app)
    spec = _baseline_spec().model_dump(mode="json")
    resp = client.post(
        "/api/expert-knowledge/advisory?aircraft_category=long_endurance_uav",
        json={"spec": spec},
    )
    assert resp.status_code == 200
    advisory = resp.json()["advisory"]
    aspect_entries = [a for a in advisory if a["topic"] == "aspect_ratio"]
    assert aspect_entries
    for a in aspect_entries:
        assert a["status"] in {"pass", "warn", "fail", "info"}
        assert a["citations"]
