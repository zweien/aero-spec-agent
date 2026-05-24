"""Twin boom geometry creation for OpenVSP."""

from typing import Any

from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult


def create_booms(adapter: Any, spec: Any) -> list[GeometryBuildResult]:
    """Create left and right boom geometries for twin_boom layout."""
    boom_length = float(spec.boom.length.value)
    boom_span = float(spec.boom.span.value)
    fuselage_length = float(spec.fuselage.length.value)
    fuselage_diameter = (
        float(spec.fuselage.max_diameter.value)
        if spec.fuselage.max_diameter
        else 0.75
    )
    boom_diameter = fuselage_diameter * 0.15

    base_x = fuselage_length * 0.40
    base_y = boom_span / 2.0
    base_z = 0.0

    left = _create_single_boom(
        adapter,
        name="left_boom",
        length=boom_length,
        diameter=boom_diameter,
        x_rel_location=base_x,
        y_offset=-base_y,
        z_rel_location=base_z,
    )
    right = _create_single_boom(
        adapter,
        name="right_boom",
        length=boom_length,
        diameter=boom_diameter,
        x_rel_location=base_x,
        y_offset=base_y,
        z_rel_location=base_z,
    )
    return [left, right]


def _create_single_boom(
    adapter: Any,
    *,
    name: str,
    length: float,
    diameter: float,
    x_rel_location: float,
    y_offset: float,
    z_rel_location: float,
) -> GeometryBuildResult:
    """Create a single boom as a slender FUSELAGE geometry."""
    geom_id = adapter.add_geom("FUSELAGE")
    adapter.set_param(geom_id, "Length", "Design", length)
    adapter.set_fuselage_diameter(geom_id, diameter)
    adapter.set_param(geom_id, "X_Rel_Location", "XForm", x_rel_location)
    adapter.set_param(geom_id, "Y_Rel_Location", "XForm", y_offset)
    adapter.set_param(geom_id, "Z_Rel_Location", "XForm", z_rel_location)

    return GeometryBuildResult(
        name=name,
        geom_id=geom_id,
        applied_parameters={
            "length": length,
            "diameter": diameter,
            "x_rel_location": x_rel_location,
            "final_y": y_offset,
            "z_rel_location": z_rel_location,
        },
    )
