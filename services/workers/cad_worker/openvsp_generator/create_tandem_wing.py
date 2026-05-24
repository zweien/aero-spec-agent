"""Tandem wing rear wing geometry creation for OpenVSP."""

from typing import Any

from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult


def create_rear_wing(adapter: Any, spec: Any) -> GeometryBuildResult:
    """Create a rear wing for tandem_wing layout, positioned behind the main wing."""
    rear_span = float(spec.rear_wing.span.value)
    rear_chord = float(spec.rear_wing.chord.value)
    sweep = float(spec.rear_wing.sweep.value) if spec.rear_wing.sweep else 0.0
    x_ratio = float(spec.rear_wing.x_position_ratio.value) if spec.rear_wing.x_position_ratio else 0.65
    gap = float(spec.rear_wing.gap.value) if spec.rear_wing.gap else 0.0
    fuselage_length = float(spec.fuselage.length.value)
    fuselage_diameter = (
        float(spec.fuselage.max_diameter.value) if spec.fuselage.max_diameter else 0.75
    )

    x_rel_location = fuselage_length * x_ratio
    z_rel_location = gap + fuselage_diameter * 0.1

    geom_id = adapter.add_geom("WING")
    adapter.set_param(geom_id, "TotalSpan", "WingGeom", rear_span)
    adapter.set_param(geom_id, "Root_Chord", "XSec_1", rear_chord)
    adapter.set_param(geom_id, "Tip_Chord", "XSec_1", rear_chord * 0.8)
    adapter.set_param(geom_id, "Sweep", "XSec_1", sweep)
    adapter.set_param(geom_id, "X_Rel_Location", "XForm", x_rel_location)
    adapter.set_param(geom_id, "Z_Rel_Location", "XForm", z_rel_location)

    return GeometryBuildResult(
        name="rear_wing",
        geom_id=geom_id,
        applied_parameters={
            "span": rear_span,
            "chord": rear_chord,
            "sweep": sweep,
            "x_rel_location": x_rel_location,
            "z_rel_location": z_rel_location,
        },
    )
