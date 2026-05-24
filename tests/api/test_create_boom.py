"""Tests for twin boom geometry creation."""

from services.workers.cad_worker.openvsp_generator.create_boom import create_booms


def _boom_spec():
    class S:
        def __init__(self, v):
            self.value = v

    class Boom:
        def __init__(self):
            self.length = S(3.0)
            self.span = S(4.0)

    class Fuselage:
        def __init__(self):
            self.length = S(6.0)
            self.max_diameter = S(0.75)

    class Wing:
        def __init__(self):
            self.span = S(10.0)
            self.root_chord = S(1.5)
            self.position = S("mid")

    class Spec:
        def __init__(self):
            self.boom = Boom()
            self.fuselage = Fuselage()
            self.wing = Wing()

    return Spec()


def test_creates_two_booms():
    from tests.api.test_openvsp_geometry_builders import make_adapter
    adapter, _fake_vsp = make_adapter()
    results = create_booms(adapter, _boom_spec())
    assert len(results) == 2
    names = {r.name for r in results}
    assert "left_boom" in names
    assert "right_boom" in names


def test_boom_position():
    from tests.api.test_openvsp_geometry_builders import make_adapter
    adapter, _fake_vsp = make_adapter()
    results = create_booms(adapter, _boom_spec())
    left = next(r for r in results if r.name == "left_boom")
    right = next(r for r in results if r.name == "right_boom")
    assert left.applied_parameters["final_y"] < 0
    assert right.applied_parameters["final_y"] > 0
    assert left.applied_parameters["length"] == 3.0
