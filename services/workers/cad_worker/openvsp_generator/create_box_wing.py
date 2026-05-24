"""Box wing geometry creation for OpenVSP."""

from typing import Any

from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult


def create_box_lower_wing(adapter: Any, spec: Any) -> GeometryBuildResult:
    """Create the lower wing for box_wing layout, positioned below the main wing."""
    gap = float(spec.box_wing_config.gap.value)
    main_span = float(spec.wing.span.value)
    root_chord = float(spec.wing.root_chord.value)
    fuselage_diameter = (
        float(spec.fuselage.max_diameter.value) if spec.fuselage.max_diameter else 0.75
    )
    fuselage_length = float(spec.fuselage.length.value)
    wing_z = fuselage_diameter * 0.1

    z_rel_location = wing_z - gap
    x_rel_location = fuselage_length * 0.40

    geom_id = adapter.add_geom("WING")
    adapter.set_param(geom_id, "TotalSpan", "WingGeom", main_span)
    adapter.set_param(geom_id, "Root_Chord", "XSec_1", root_chord)
    adapter.set_param(geom_id, "Tip_Chord", "XSec_1", root_chord * 0.4)
    adapter.set_param(geom_id, "Sweep", "XSec_1", 0.0)
    adapter.set_param(geom_id, "X_Rel_Location", "XForm", x_rel_location)
    adapter.set_param(geom_id, "Z_Rel_Location", "XForm", z_rel_location)

    return GeometryBuildResult(
        name="box_lower_wing",
        geom_id=geom_id,
        applied_parameters={
            "span": main_span,
            "chord": root_chord,
            "gap": gap,
            "x_rel_location": x_rel_location,
            "z_rel_location": z_rel_location,
        },
    )


def create_endplates(adapter: Any, spec: Any) -> list[GeometryBuildResult]:
    """Create vertical endplate wings connecting upper and lower wings at the tips."""
    gap = float(spec.box_wing_config.gap.value)
    endplate_chord = (
        float(spec.box_wing_config.endplate_chord.value)
        if spec.box_wing_config.endplate_chord else 0.3
    )
    main_span = float(spec.wing.span.value)
    fuselage_length = float(spec.fuselage.length.value)
    fuselage_diameter = (
        float(spec.fuselage.max_diameter.value) if spec.fuselage.max_diameter else 0.75
    )

    wing_x = fuselage_length * 0.40
    wing_z = fuselage_diameter * 0.1
    z_mid = wing_z - gap / 2.0

    results = []
    for name, y_offset in [("left_endplate", -main_span / 2.0), ("right_endplate", main_span / 2.0)]:
        geom_id = adapter.add_geom("WING")
        adapter.set_param(geom_id, "TotalSpan", "WingGeom", gap)
        adapter.set_param(geom_id, "Root_Chord", "XSec_1", endplate_chord)
        adapter.set_param(geom_id, "Tip_Chord", "XSec_1", endplate_chord)
        adapter.set_param(geom_id, "X_Rel_Location", "XForm", wing_x)
        adapter.set_param(geom_id, "Y_Rel_Location", "XForm", y_offset)
        adapter.set_param(geom_id, "Z_Rel_Location", "XForm", z_mid)
        adapter.set_param(geom_id, "X_Rel_Rotation", "XForm", 90.0)

        results.append(GeometryBuildResult(
            name=name,
            geom_id=geom_id,
            applied_parameters={
                "span": gap,
                "chord": endplate_chord,
                "y_offset": y_offset,
                "x_rel_rotation": 90.0,
            },
        ))

    return results
