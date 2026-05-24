"""Tests for multi-section wing creation."""

from services.workers.cad_worker.openvsp_generator.create_wing import create_main_wing
from services.workers.cad_worker.openvsp_generator.openvsp_adapter import OpenVspAdapter
from tests.api.test_openvsp_backend_unit import FakeOpenVspModule


def _make_adapter():
    return OpenVspAdapter(module=FakeOpenVspModule())


def _wing_spec(
    sections: int | None = None,
    inner_sweep: float | None = None,
    inner_dihedral: float | None = None,
):
    class S:
        def __init__(self, v):
            self.value = v

    class Wing:
        def __init__(self):
            self.position = S("mid")
            self.span = S(12.0)
            self.root_chord = S(1.5)
            self.tip_chord = S(0.8)
            self.sweep = S(5.0)
            self.dihedral = S(3.0)
            self.sections = S(sections) if sections is not None else None
            self.inner_sweep = S(inner_sweep) if inner_sweep is not None else None
            self.inner_dihedral = (
                S(inner_dihedral) if inner_dihedral is not None else None
            )

    class Fuselage:
        def __init__(self):
            self.length = S(6.0)
            self.max_diameter = S(0.75)

    class Spec:
        def __init__(self):
            self.wing = Wing()
            self.fuselage = Fuselage()

    return Spec()


def test_single_section_returns_one_result():
    adapter = _make_adapter()
    result = create_main_wing(adapter, _wing_spec())
    assert result.name == "main_wing"
    assert isinstance(result.applied_parameters["span"], float)


def test_two_section_returns_list():
    adapter = _make_adapter()
    results = create_main_wing(
        adapter, _wing_spec(sections=2, inner_sweep=15.0, inner_dihedral=5.0)
    )
    assert isinstance(results, list)
    assert len(results) == 2
    names = [r.name for r in results]
    assert "inner_wing" in names
    assert "outer_wing" in names


def test_three_section_returns_three():
    adapter = _make_adapter()
    results = create_main_wing(
        adapter, _wing_spec(sections=3, inner_sweep=20.0, inner_dihedral=2.0)
    )
    assert len(results) == 3


def test_outer_wing_uses_inner_params():
    adapter = _make_adapter()
    results = create_main_wing(
        adapter, _wing_spec(sections=2, inner_sweep=15.0, inner_dihedral=5.0)
    )
    outer = next(r for r in results if r.name == "outer_wing")
    assert outer.applied_parameters["sweep"] == 15.0
    assert outer.applied_parameters["dihedral"] == 5.0


def test_multi_section_spans_sum_to_total():
    adapter = _make_adapter()
    total_span = 12.0
    results = create_main_wing(
        adapter, _wing_spec(sections=3, inner_sweep=20.0, inner_dihedral=2.0)
    )
    span_sum = sum(r.applied_parameters["span"] for r in results)
    assert span_sum == total_span


def test_multi_section_chords_are_linear():
    """Chords should decrease linearly from root_chord to tip_chord."""
    adapter = _make_adapter()
    root_chord = 1.5
    tip_chord = 0.8
    results = create_main_wing(
        adapter, _wing_spec(sections=3, inner_sweep=20.0, inner_dihedral=2.0)
    )
    chords = [r.applied_parameters["root_chord"] for r in results]
    # With 3 sections, chord breaks: root_chord, root+1/3*(tip-root), root+2/3*(tip-root)
    for i, c in enumerate(chords):
        expected = root_chord + i * (tip_chord - root_chord) / 3
        assert c == expected, f"Section {i}: expected {expected}, got {c}"


def test_single_section_spec_returns_same_span():
    adapter = _make_adapter()
    result = create_main_wing(adapter, _wing_spec())
    assert result.applied_parameters["span"] == 12.0


def test_sections_none_returns_single():
    """When sections is None, should behave as single-section."""
    adapter = _make_adapter()
    result = create_main_wing(adapter, _wing_spec(sections=None))
    assert result.name == "main_wing"
