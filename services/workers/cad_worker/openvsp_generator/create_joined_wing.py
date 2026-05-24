"""Joined wing rear wing geometry creation for OpenVSP."""

from typing import Any

from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult


def create_rear_wing(adapter: Any, spec: Any) -> GeometryBuildResult:
    """Create the rear (joined) wing for joined_wing layout.

    The rear wing has negative sweep (forward-swept) to join the main wing at the tips.
    """
    rear_span = float(spec.rear_wing.span.value)
    rear_chord = float(spec.rear_wing.chord.value)
    sweep = float(spec.rear_wing.sweep.value) if spec.rear_wing.sweep else -15.0
    x_ratio = float(spec.rear_wing.x_position_ratio.value) if spec.rear_wing.x_position_ratio else 0.70
    fuselage_length = float(spec.fuselage.length.value)

    x_rel_location = fuselage_length * x_ratio

    geom_id = adapter.add_geom("WING")
    adapter.set_param(geom_id, "TotalSpan", "WingGeom", rear_span)
    adapter.set_param(geom_id, "Root_Chord", "XSec_1", rear_chord)
    adapter.set_param(geom_id, "Tip_Chord", "XSec_1", rear_chord * 0.6)
    adapter.set_param(geom_id, "Sweep", "XSec_1", sweep)
    adapter.set_param(geom_id, "X_Rel_Location", "XForm", x_rel_location)

    return GeometryBuildResult(
        name="joined_rear_wing",
        geom_id=geom_id,
        applied_parameters={
            "span": rear_span,
            "chord": rear_chord,
            "sweep": sweep,
            "x_rel_location": x_rel_location,
        },
    )
