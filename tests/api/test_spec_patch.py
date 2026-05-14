from pathlib import Path

import pytest

from services.api.app.services.spec_io import load_aircraft_spec
from services.api.app.services.spec_patch import apply_patch


EXAMPLE = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml")


def test_apply_patch_changes_wing_span():
    spec = load_aircraft_spec(EXAMPLE)
    patched = apply_patch(spec, [{"path": "wing.span.value", "value": 14.0}])
    assert patched.wing.span.value == 14.0
    assert patched.fuselage.length.value == spec.fuselage.length.value


def test_apply_patch_adds_missing_optional_field():
    spec = load_aircraft_spec(EXAMPLE)
    assert spec.wing.sweep is not None
    patched = apply_patch(spec, [{"path": "wing.sweep.value", "value": 10}])
    assert patched.wing.sweep is not None
    assert patched.wing.sweep.value == 10


def test_apply_patch_rejects_invalid_path():
    spec = load_aircraft_spec(EXAMPLE)
    with pytest.raises(KeyError, match="nonexistent"):
        apply_patch(spec, [{"path": "nonexistent.field", "value": 1}])


def test_apply_patch_validates_result():
    spec = load_aircraft_spec(EXAMPLE)
    with pytest.raises(Exception):
        apply_patch(spec, [{"path": "schema_version", "value": "99.0"}])


def test_apply_patch_source_field():
    spec = load_aircraft_spec(EXAMPLE)
    patched = apply_patch(spec, [
        {"path": "wing.span.value", "value": 14.0},
        {"path": "wing.span.source", "value": "user"},
        {"path": "wing.span.confidence", "value": 1.0},
    ])
    assert patched.wing.span.value == 14.0
    assert patched.wing.span.source == "user"
    assert patched.wing.span.confidence == 1.0
