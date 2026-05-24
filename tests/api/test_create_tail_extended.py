"""Tests for extended tail configurations: v_tail, inverted_v, cruciform."""

from tests.api.test_openvsp_geometry_builders import make_adapter
from services.workers.cad_worker.openvsp_generator.create_tail import create_tail


def _make_spec(
    tail_type: str = "conventional",
    wing_span: float = 10.0,
    root_chord: float = 1.5,
    fuselage_length: float = 6.0,
):
    """Create a minimal spec-like object for tail creation."""

    class Scalar:
        def __init__(self, v):
            self.value = v

    class Tail:
        def __init__(self, t):
            self.type = Scalar(t)

    class Wing:
        def __init__(self):
            self.span = Scalar(wing_span)
            self.root_chord = Scalar(root_chord)

    class Fuselage:
        def __init__(self):
            self.length = Scalar(fuselage_length)

    class Spec:
        def __init__(self, tail_type_str):
            self.tail = Tail(tail_type_str)
            self.wing = Wing()
            self.fuselage = Fuselage()

    return Spec(tail_type)


def test_v_tail_creates_single_surface():
    adapter, _ = make_adapter()
    results = create_tail(adapter, _make_spec("v_tail"))
    assert len(results) == 1
    assert results[0].name == "v_tail"


def test_v_tail_rotation_angle():
    adapter, _ = make_adapter()
    results = create_tail(adapter, _make_spec("v_tail"))
    assert results[0].applied_parameters.get("x_rel_rotation") == 45.0


def test_inverted_v_rotation_angle():
    adapter, _ = make_adapter()
    results = create_tail(adapter, _make_spec("inverted_v"))
    assert len(results) == 1
    assert results[0].name == "inverted_v_tail"
    assert results[0].applied_parameters.get("x_rel_rotation") == -45.0


def test_cruciform_has_two_surfaces():
    adapter, _ = make_adapter()
    results = create_tail(adapter, _make_spec("cruciform"))
    assert len(results) == 2
    names = {r.name for r in results}
    assert "vertical_tail" in names
    assert "cruciform_htail" in names


def test_cruciform_htail_elevated():
    adapter, _ = make_adapter()
    results = create_tail(adapter, _make_spec("cruciform"))
    cf = next(r for r in results if r.name == "cruciform_htail")
    assert cf.applied_parameters.get("z_rel_location") is not None
    assert cf.applied_parameters["z_rel_location"] > 0


def test_conventional_unchanged():
    adapter, _ = make_adapter()
    results = create_tail(adapter, _make_spec("conventional"))
    names = {r.name for r in results}
    assert names == {"horizontal_tail", "vertical_tail"}
