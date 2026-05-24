from copy import deepcopy
from typing import Any

import pytest

from services.api.app.services.spec_io import load_aircraft_spec
from services.workers.cad_worker.openvsp_generator.create_engine import (
    create_engine_nacelles,
)
from services.workers.cad_worker.openvsp_generator.openvsp_adapter import OpenVspAdapter
from tests.api.test_openvsp_geometry_builders import (
    FakeOpenVspModule,
    valid_spec_data,
)


def make_adapter():
    fake_vsp = FakeOpenVspModule()
    return OpenVspAdapter(module=fake_vsp), fake_vsp


def _make_spec(count: int, position: str | None = None) -> Any:
    data = deepcopy(valid_spec_data())
    data["engine"]["count"]["value"] = count
    if position is not None:
        data["engine"]["position"] = {
            "value": position,
            "source": "user",
            "confidence": 1.0,
        }
    return load_aircraft_spec(data)


def test_three_engines_creates_three_nacelles():
    spec = _make_spec(3)
    adapter, _fake_vsp = make_adapter()

    results = create_engine_nacelles(adapter, spec)

    assert len(results) == 3
    names = [r.name for r in results]
    assert "center_engine" in names
    assert "left_engine" in names
    assert "right_engine" in names
    for r in results:
        assert r.applied_parameters["engine.count"] == 3


def test_four_engines_creates_four_nacelles():
    spec = _make_spec(4)
    adapter, _fake_vsp = make_adapter()

    results = create_engine_nacelles(adapter, spec)

    assert len(results) == 4
    names = [r.name for r in results]
    assert "left_inner_engine" in names
    assert "left_outer_engine" in names
    assert "right_inner_engine" in names
    assert "right_outer_engine" in names
    for r in results:
        assert r.applied_parameters["engine.count"] == 4


def test_wing_tip_position():
    spec = _make_spec(2, position="wing_tip")
    adapter, _fake_vsp = make_adapter()

    results = create_engine_nacelles(adapter, spec)

    assert len(results) == 2
    # wing_tip places engines at wing_span * 0.48
    wing_span = float(spec.wing.span.value)
    expected_base_y = wing_span * 0.48
    for r in results:
        assert r.applied_parameters["base_y"] == pytest.approx(expected_base_y)
    # y_offset magnitude should be large (>= wing_span * 0.4)
    for r in results:
        assert abs(r.applied_parameters["final_y"]) >= wing_span * 0.4


def test_over_wing_position():
    spec = _make_spec(2, position="over_wing")
    adapter, _fake_vsp = make_adapter()

    results = create_engine_nacelles(adapter, spec)

    assert len(results) == 2
    # over_wing should have positive z (above wing)
    for r in results:
        assert r.applied_parameters["base_z"] > 0
        assert r.applied_parameters["final_z"] > 0


def test_pusher_position():
    spec = _make_spec(1, position="pusher")
    adapter, _fake_vsp = make_adapter()

    results = create_engine_nacelles(adapter, spec)

    assert len(results) == 1
    assert results[0].name == "center_engine"
    assert results[0].applied_parameters["engine.count"] == 1
