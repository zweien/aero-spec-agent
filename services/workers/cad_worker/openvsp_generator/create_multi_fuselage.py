"""Multi-fuselage geometry creation for OpenVSP."""

from typing import Any

from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult


def create_multi_fuselage(adapter: Any, spec: Any) -> list[GeometryBuildResult]:
    """Create left and right fuselage geometries for multi_fuselage layout."""
    spacing = float(spec.multi_fuselage.spacing.value)
    fuselage_length = float(spec.fuselage.length.value)
    fuselage_diameter = (
        float(spec.fuselage.max_diameter.value) if spec.fuselage.max_diameter else 0.75
    )

    y_offset = spacing / 2.0

    left = _create_single_fuselage(
        adapter,
        name="left_fuselage",
        length=fuselage_length,
        diameter=fuselage_diameter,
        y_offset=-y_offset,
    )
    right = _create_single_fuselage(
        adapter,
        name="right_fuselage",
        length=fuselage_length,
        diameter=fuselage_diameter,
        y_offset=y_offset,
    )
    return [left, right]


def _create_single_fuselage(
    adapter: Any,
    *,
    name: str,
    length: float,
    diameter: float,
    y_offset: float,
) -> GeometryBuildResult:
    geom_id = adapter.add_geom("FUSELAGE")
    adapter.set_param(geom_id, "Length", "Design", length)
    adapter.set_fuselage_diameter(geom_id, diameter)
    adapter.set_param(geom_id, "Y_Rel_Location", "XForm", y_offset)

    return GeometryBuildResult(
        name=name,
        geom_id=geom_id,
        applied_parameters={
            "length": length,
            "diameter": diameter,
            "y_offset": y_offset,
        },
    )
