"""Canard foreplane geometry creation for OpenVSP."""

from typing import Any

from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult


def create_canard(adapter: Any, spec: Any) -> GeometryBuildResult:
    """Create a canard foreplane geometry positioned ahead of the main wing."""
    canard_span = float(spec.canard.span.value)
    canard_chord = float(spec.canard.chord.value)
    sweep = float(spec.canard.sweep.value) if spec.canard.sweep else 5.0
    x_ratio = float(spec.canard.x_position_ratio.value) if spec.canard.x_position_ratio else 0.15
    fuselage_length = float(spec.fuselage.length.value)

    x_rel_location = fuselage_length * x_ratio

    geom_id = adapter.add_geom("WING")
    adapter.set_param(geom_id, "TotalSpan", "WingGeom", canard_span)
    adapter.set_param(geom_id, "Root_Chord", "XSec_1", canard_chord)
    adapter.set_param(geom_id, "Tip_Chord", "XSec_1", canard_chord * 0.7)
    adapter.set_param(geom_id, "Sweep", "XSec_1", sweep)
    adapter.set_param(geom_id, "X_Rel_Location", "XForm", x_rel_location)

    return GeometryBuildResult(
        name="canard",
        geom_id=geom_id,
        applied_parameters={
            "span": canard_span,
            "chord": canard_chord,
            "sweep": sweep,
            "x_rel_location": x_rel_location,
        },
    )
