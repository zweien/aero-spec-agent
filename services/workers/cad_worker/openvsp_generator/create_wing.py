from typing import Any

from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult


def _value(scalar: Any, default: float | None = None) -> float:
    if scalar is None:
        if default is None:
            raise ValueError("missing required scalar")
        return default
    return float(scalar.value)


def _wing_z_location(position: str, fuselage_diameter: float) -> float:
    factors = {
        "high": 0.45,
        "mid": 0.0,
        "low": -0.45,
    }
    return factors.get(position, 0.0) * fuselage_diameter


def create_main_wing(adapter: Any, spec: Any) -> GeometryBuildResult:
    geom_id = adapter.add_geom("WING")
    span = _value(spec.wing.span)
    root_chord = _value(spec.wing.root_chord)
    tip_chord = _value(spec.wing.tip_chord)
    sweep = _value(spec.wing.sweep, 0.0)
    dihedral = _value(spec.wing.dihedral, 0.0)
    fuselage_diameter = _value(spec.fuselage.max_diameter, 0.75)
    position = str(spec.wing.position.value).lower()
    z_rel_location = _wing_z_location(position, fuselage_diameter)

    adapter.set_param(geom_id, "TotalSpan", "WingGeom", span)
    adapter.set_param(geom_id, "Root_Chord", "XSec_1", root_chord)
    adapter.set_param(geom_id, "Tip_Chord", "XSec_1", tip_chord)
    adapter.set_param(geom_id, "Sweep", "XSec_1", sweep)
    adapter.set_param(geom_id, "Dihedral", "XSec_1", dihedral)
    adapter.set_param(geom_id, "Z_Rel_Location", "XForm", z_rel_location)

    return GeometryBuildResult(
        name="main_wing",
        geom_id=geom_id,
        applied_parameters={
            "span": span,
            "root_chord": root_chord,
            "tip_chord": tip_chord,
            "sweep": sweep,
            "dihedral": dihedral,
            "z_rel_location": z_rel_location,
        },
    )
