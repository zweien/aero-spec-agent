from typing import Any

from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult


def _value(scalar: Any, default: float | None = None) -> float:
    if scalar is None:
        if default is None:
            raise ValueError("missing required scalar")
        return default
    return float(scalar.value)


def create_fuselage(adapter: Any, spec: Any) -> GeometryBuildResult:
    geom_id = adapter.add_geom("FUSELAGE")
    length = _value(spec.fuselage.length)
    diameter = _value(spec.fuselage.max_diameter, 0.75)

    adapter.set_param(geom_id, "Length", "Design", length)
    adapter.set_fuselage_diameter(geom_id, diameter)

    return GeometryBuildResult(
        name="fuselage",
        geom_id=geom_id,
        applied_parameters={
            "length": length,
            "max_diameter": diameter,
        },
    )
