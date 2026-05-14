from copy import deepcopy
from typing import Any

import pytest

from services.api.app.services.spec_io import load_aircraft_spec
from services.workers.cad_worker.openvsp_generator.create_engine import (
    _create_engine_nacelle,
    create_engine_nacelles,
)
from services.workers.cad_worker.openvsp_generator.create_fuselage import (
    create_fuselage,
)
from services.workers.cad_worker.openvsp_generator.create_tail import create_tail
from services.workers.cad_worker.openvsp_generator.create_wing import create_main_wing
from services.workers.cad_worker.openvsp_generator.errors import (
    CadGenerationError,
    UnsupportedGeometryError,
)
from services.workers.cad_worker.openvsp_generator.openvsp_adapter import OpenVspAdapter


def valid_spec_data() -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "aircraft": {
            "name": "typed",
            "type": "fixed_wing_uav",
            "layout": "conventional",
        },
        "mission": {},
        "fuselage": {
            "length": {
                "value": 7.0,
                "unit": "m",
                "source": "user",
                "confidence": 1.0,
            },
            "max_diameter": {
                "value": 0.75,
                "unit": "m",
                "source": "rule_default",
                "confidence": 0.8,
            },
        },
        "wing": {
            "position": {"value": "high", "source": "user", "confidence": 1.0},
            "span": {
                "value": 12.0,
                "unit": "m",
                "source": "user",
                "confidence": 1.0,
            },
            "root_chord": {
                "value": 1.2,
                "unit": "m",
                "source": "rule_default",
                "confidence": 0.8,
            },
            "tip_chord": {
                "value": 0.6,
                "unit": "m",
                "source": "rule_default",
                "confidence": 0.8,
            },
            "sweep": {
                "value": 5.0,
                "unit": "deg",
                "source": "rule_default",
                "confidence": 0.8,
            },
            "dihedral": {
                "value": 3.0,
                "unit": "deg",
                "source": "rule_default",
                "confidence": 0.8,
            },
        },
        "tail": {"type": {"value": "conventional", "source": "user", "confidence": 1.0}},
        "engine": {"count": {"value": 2, "source": "user", "confidence": 1.0}},
    }


class FakeOpenVspModule:
    _ALLOWED_PARAMETERS = {
        "FUSELAGE": {
            ("Length", "Design"),
        },
        "WING": {
            ("TotalSpan", "WingGeom"),
            ("Root_Chord", "XSec_1"),
            ("Tip_Chord", "XSec_1"),
            ("Sweep", "XSec_1"),
            ("Dihedral", "XSec_1"),
            ("X_Rel_Location", "XForm"),
            ("X_Rel_Rotation", "XForm"),
            ("Z_Rel_Location", "XForm"),
        },
        "POD": {
            ("X_Rel_Location", "XForm"),
            ("Y_Rel_Location", "XForm"),
            ("Z_Rel_Location", "XForm"),
            ("Length", "Design"),
            ("FineRatio", "Design"),
        },
    }

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.geom_kinds: dict[str, str] = {}
        self.next_index = 1
        self.xsec_surfs: dict[str, str] = {}
        self.xsecs: dict[tuple[str, int], str] = {}

    def AddGeom(self, kind: str, parent_id: str) -> str:
        geom_id = f"geom-{self.next_index}"
        self.next_index += 1
        self.geom_kinds[geom_id] = kind
        self.calls.append(("AddGeom", kind, parent_id, geom_id))
        return geom_id

    def FindParm(self, geom_id: str, parm_name: str, group_name: str) -> str:
        self.calls.append(("FindParm", geom_id, parm_name, group_name))
        kind = self.geom_kinds[geom_id]
        if (parm_name, group_name) not in self._ALLOWED_PARAMETERS[kind]:
            return ""
        return f"parm:{geom_id}:{parm_name}:{group_name}"

    def SetParmVal(self, parm_id: str, value: float | int | str) -> None:
        self.calls.append(("SetParmVal", parm_id, value))

    def GetXSecSurf(self, geom_id: str, index: int) -> str:
        surf_id = f"xsec-surf:{geom_id}:{index}"
        self.xsec_surfs[geom_id] = surf_id
        self.calls.append(("GetXSecSurf", geom_id, index, surf_id))
        return surf_id

    def GetNumXSec(self, xsec_surf_id: str) -> int:
        self.calls.append(("GetNumXSec", xsec_surf_id))
        return 5

    def GetXSec(self, xsec_surf_id: str, index: int) -> str:
        xsec_id = f"xsec:{xsec_surf_id}:{index}"
        self.xsecs[(xsec_surf_id, index)] = xsec_id
        self.calls.append(("GetXSec", xsec_surf_id, index, xsec_id))
        return xsec_id

    def SetXSecWidthHeight(self, xsec_id: str, width: float, height: float) -> None:
        self.calls.append(("SetXSecWidthHeight", xsec_id, width, height))

    def value_for(self, geom_id: str, parm_name: str, group_name: str) -> float | int | str:
        parm_id = f"parm:{geom_id}:{parm_name}:{group_name}"
        for call in self.calls:
            if call[0] == "SetParmVal" and call[1] == parm_id:
                return call[2]
        raise AssertionError(f"Missing SetParmVal for {parm_id}")


def make_adapter() -> tuple[OpenVspAdapter, FakeOpenVspModule]:
    fake_vsp = FakeOpenVspModule()
    return OpenVspAdapter(module=fake_vsp), fake_vsp


def test_create_fuselage_applies_length_and_diameter():
    spec = load_aircraft_spec(valid_spec_data())
    adapter, fake_vsp = make_adapter()

    result = create_fuselage(adapter, spec)

    assert result.name == "fuselage"
    assert result.geom_id == "geom-1"
    assert result.applied_parameters == {"length": 7.0, "max_diameter": 0.75}
    assert ("AddGeom", "FUSELAGE", "", "geom-1") in fake_vsp.calls
    assert fake_vsp.value_for("geom-1", "Length", "Design") == 7.0
    assert ("FindParm", "geom-1", "Diameter", "Design") not in fake_vsp.calls
    assert (
        "SetXSecWidthHeight",
        "xsec:xsec-surf:geom-1:0:1",
        0.75,
        0.75,
    ) in fake_vsp.calls


def test_create_fuselage_defaults_missing_diameter_to_075():
    data = valid_spec_data()
    del data["fuselage"]["max_diameter"]
    spec = load_aircraft_spec(data)
    adapter, fake_vsp = make_adapter()

    result = create_fuselage(adapter, spec)

    assert result.applied_parameters["max_diameter"] == 0.75
    assert (
        "SetXSecWidthHeight",
        "xsec:xsec-surf:geom-1:0:1",
        0.75,
        0.75,
    ) in fake_vsp.calls


def test_create_main_wing_applies_planform_and_high_wing_z_location():
    spec = load_aircraft_spec(valid_spec_data())
    adapter, fake_vsp = make_adapter()

    result = create_main_wing(adapter, spec)

    assert result.name == "main_wing"
    assert result.geom_id == "geom-1"
    assert result.applied_parameters == {
        "span": 12.0,
        "root_chord": 1.2,
        "tip_chord": 0.6,
        "sweep": 5.0,
        "dihedral": 3.0,
        "z_rel_location": pytest.approx(0.3375),
    }
    assert fake_vsp.value_for("geom-1", "TotalSpan", "WingGeom") == 12.0
    assert fake_vsp.value_for("geom-1", "Root_Chord", "XSec_1") == 1.2
    assert fake_vsp.value_for("geom-1", "Tip_Chord", "XSec_1") == 0.6
    assert fake_vsp.value_for("geom-1", "Sweep", "XSec_1") == 5.0
    assert fake_vsp.value_for("geom-1", "Dihedral", "XSec_1") == 3.0
    assert fake_vsp.value_for("geom-1", "Z_Rel_Location", "XForm") == pytest.approx(
        0.3375
    )


def test_create_main_wing_uses_zero_z_location_for_unknown_wing_position():
    data = valid_spec_data()
    data["wing"]["position"]["value"] = "shoulder"
    spec = load_aircraft_spec(data)
    adapter, fake_vsp = make_adapter()

    result = create_main_wing(adapter, spec)

    assert result.applied_parameters["z_rel_location"] == 0.0
    assert fake_vsp.value_for("geom-1", "Z_Rel_Location", "XForm") == 0.0


def test_create_tail_returns_horizontal_and_vertical_tail_results():
    spec = load_aircraft_spec(valid_spec_data())
    adapter, fake_vsp = make_adapter()

    horizontal_tail, vertical_tail = create_tail(adapter, spec)

    assert horizontal_tail.name == "horizontal_tail"
    assert vertical_tail.name == "vertical_tail"
    assert horizontal_tail.applied_parameters == {
        "span": pytest.approx(3.36),
        "chord": pytest.approx(0.54),
        "x_rel_location": pytest.approx(2.94),
    }
    assert vertical_tail.applied_parameters == {
        "span": pytest.approx(1.92),
        "chord": pytest.approx(0.66),
        "x_rel_location": pytest.approx(2.94),
        "x_rel_rotation": 90.0,
    }
    assert ("AddGeom", "WING", "", "geom-1") in fake_vsp.calls
    assert ("AddGeom", "WING", "", "geom-2") in fake_vsp.calls
    assert fake_vsp.value_for("geom-1", "TotalSpan", "WingGeom") == pytest.approx(3.36)
    assert fake_vsp.value_for("geom-2", "TotalSpan", "WingGeom") == pytest.approx(1.92)
    assert ("FindParm", "geom-2", "X_Rel_Rotation", "XForm") in fake_vsp.calls
    assert fake_vsp.value_for("geom-2", "X_Rel_Rotation", "XForm") == 90.0


def test_create_engine_nacelles_returns_two_symmetric_pods():
    spec = load_aircraft_spec(valid_spec_data())
    adapter, fake_vsp = make_adapter()

    left_engine, right_engine = create_engine_nacelles(adapter, spec)

    assert left_engine.name == "left_engine"
    assert right_engine.name == "right_engine"
    assert left_engine.applied_parameters["engine.count"] == 2
    assert right_engine.applied_parameters["engine.count"] == 2
    assert left_engine.applied_parameters["y_offset"] == pytest.approx(-3.0)
    assert right_engine.applied_parameters["y_offset"] == pytest.approx(3.0)
    assert left_engine.applied_parameters["diameter"] == pytest.approx(0.375)
    assert right_engine.applied_parameters["diameter"] == pytest.approx(0.375)
    assert left_engine.applied_parameters["fineness_ratio"] == pytest.approx(6.4)
    assert right_engine.applied_parameters["fineness_ratio"] == pytest.approx(6.4)
    assert fake_vsp.value_for("geom-1", "Y_Rel_Location", "XForm") == pytest.approx(-3.0)
    assert fake_vsp.value_for("geom-2", "Y_Rel_Location", "XForm") == pytest.approx(3.0)
    assert fake_vsp.value_for("geom-1", "Length", "Design") == pytest.approx(1.2)
    assert fake_vsp.value_for("geom-2", "FineRatio", "Design") == pytest.approx(6.4)
    assert ("FindParm", "geom-2", "FineRatio", "Design") in fake_vsp.calls
    assert ("FindParm", "geom-2", "Diameter", "Design") not in fake_vsp.calls


def test_create_engine_nacelle_rejects_non_positive_diameter():
    adapter, _fake_vsp = make_adapter()

    with pytest.raises(CadGenerationError, match="diameter"):
        _create_engine_nacelle(
            adapter,
            name="left_engine",
            engine_count=2,
            x_rel_location=0.3,
            y_offset=-3.0,
            z_rel_location=-0.3375,
            length=1.2,
            diameter=0.0,
        )


def test_create_engine_nacelles_single_engine_creates_center_pod():
    data = deepcopy(valid_spec_data())
    data["engine"]["count"]["value"] = 1
    data["engine"]["position"] = {"value": "nose", "source": "user", "confidence": 1.0}
    spec = load_aircraft_spec(data)
    adapter, fake_vsp = make_adapter()

    results = create_engine_nacelles(adapter, spec)

    assert len(results) == 1
    assert results[0].name == "center_engine"
    assert results[0].applied_parameters["engine.count"] == 1
    assert results[0].applied_parameters["y_offset"] == pytest.approx(0.0)


def test_create_engine_nacelles_rejects_unsupported_engine_count():
    data = deepcopy(valid_spec_data())
    data["engine"]["count"]["value"] = 3
    spec = load_aircraft_spec(data)
    adapter, _fake_vsp = make_adapter()

    with pytest.raises(UnsupportedGeometryError, match="engine.count"):
        create_engine_nacelles(adapter, spec)
