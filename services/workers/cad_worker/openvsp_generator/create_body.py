"""BWB flat body geometry creation for OpenVSP."""

from typing import Any

from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult


def _value(scalar: Any, default: float | None = None) -> float:
    if scalar is None:
        if default is None:
            raise ValueError("missing required scalar")
        return default
    return float(scalar.value)


def create_flat_body(adapter: Any, spec: Any) -> GeometryBuildResult:
    """Create a BWB flat body using a FUSELAGE geometry with non-circular cross-section."""
    length = _value(spec.fuselage.length)
    width = _value(spec.body.width)
    height = _value(spec.body.height)

    geom_id = adapter.add_geom("FUSELAGE")
    adapter.set_param(geom_id, "Length", "Design", length)
    adapter.set_fuselage_cross_section(geom_id, width, height)

    return GeometryBuildResult(
        name="flat_body",
        geom_id=geom_id,
        applied_parameters={
            "length": length,
            "width": width,
            "height": height,
        },
    )
