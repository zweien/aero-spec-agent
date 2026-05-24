"""Biplane lower wing geometry creation for OpenVSP."""

from typing import Any

from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult


def create_lower_wing(adapter: Any, spec: Any) -> GeometryBuildResult:
    """Create the lower wing for biplane layout."""
    lower_span = float(spec.second_wing.span.value)
    lower_chord = float(spec.second_wing.chord.value)
    sweep = float(spec.second_wing.sweep.value) if spec.second_wing.sweep else 0.0
    gap = float(spec.second_wing.gap.value)
    stagger = float(spec.second_wing.stagger.value) if spec.second_wing.stagger else 0.0
    dihedral = float(spec.second_wing.dihedral.value) if spec.second_wing.dihedral else 0.0
    fuselage_length = float(spec.fuselage.length.value)
    fuselage_diameter = (
        float(spec.fuselage.max_diameter.value) if spec.fuselage.max_diameter else 0.75
    )

    wing_x = fuselage_length * 0.40
    wing_z = fuselage_diameter * 0.1

    x_rel_location = wing_x + stagger
    z_rel_location = wing_z - gap

    geom_id = adapter.add_geom("WING")
    adapter.set_param(geom_id, "TotalSpan", "WingGeom", lower_span)
    adapter.set_param(geom_id, "Root_Chord", "XSec_1", lower_chord)
    adapter.set_param(geom_id, "Tip_Chord", "XSec_1", lower_chord * 0.8)
    adapter.set_param(geom_id, "Sweep", "XSec_1", sweep)
    adapter.set_param(geom_id, "Dihedral", "XSec_1", dihedral)
    adapter.set_param(geom_id, "X_Rel_Location", "XForm", x_rel_location)
    adapter.set_param(geom_id, "Z_Rel_Location", "XForm", z_rel_location)

    return GeometryBuildResult(
        name="lower_wing",
        geom_id=geom_id,
        applied_parameters={
            "span": lower_span,
            "chord": lower_chord,
            "sweep": sweep,
            "dihedral": dihedral,
            "gap": gap,
            "stagger": stagger,
            "x_rel_location": x_rel_location,
            "z_rel_location": z_rel_location,
        },
    )
