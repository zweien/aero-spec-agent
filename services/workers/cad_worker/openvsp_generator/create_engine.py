from typing import Any

from services.workers.cad_worker.openvsp_generator.errors import UnsupportedGeometryError
from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult


def create_engine_nacelles(adapter: Any, spec: Any) -> list[GeometryBuildResult]:
    engine_count = int(spec.engine.count.value)
    if engine_count != 2:
        raise UnsupportedGeometryError(
            f"Unsupported OpenVSP geometry for engine.count={engine_count}"
        )

    wing_span = float(spec.wing.span.value)
    root_chord = float(spec.wing.root_chord.value)
    fuselage_diameter = (
        float(spec.fuselage.max_diameter.value)
        if spec.fuselage.max_diameter is not None
        else 0.75
    )

    x_rel_location = root_chord * 0.25
    y_offset = wing_span * 0.25
    z_rel_location = -fuselage_diameter * 0.45
    length = root_chord
    diameter = fuselage_diameter * 0.5

    return [
        _create_engine_nacelle(
            adapter,
            name="left_engine",
            engine_count=engine_count,
            x_rel_location=x_rel_location,
            y_rel_location=-y_offset,
            z_rel_location=z_rel_location,
            length=length,
            diameter=diameter,
        ),
        _create_engine_nacelle(
            adapter,
            name="right_engine",
            engine_count=engine_count,
            x_rel_location=x_rel_location,
            y_rel_location=y_offset,
            z_rel_location=z_rel_location,
            length=length,
            diameter=diameter,
        ),
    ]


def _create_engine_nacelle(
    adapter: Any,
    *,
    name: str,
    engine_count: int,
    x_rel_location: float,
    y_rel_location: float,
    z_rel_location: float,
    length: float,
    diameter: float,
) -> GeometryBuildResult:
    geom_id = adapter.add_geom("POD")

    adapter.set_param(geom_id, "X_Rel_Location", "XForm", x_rel_location)
    adapter.set_param(geom_id, "Y_Rel_Location", "XForm", y_rel_location)
    adapter.set_param(geom_id, "Z_Rel_Location", "XForm", z_rel_location)
    adapter.set_param(geom_id, "Length", "Design", length)
    adapter.set_param(geom_id, "Diameter", "Design", diameter)

    return GeometryBuildResult(
        name=name,
        geom_id=geom_id,
        applied_parameters={
            "engine.count": engine_count,
            "x_rel_location": x_rel_location,
            "y_rel_location": y_rel_location,
            "z_rel_location": z_rel_location,
            "length": length,
            "diameter": diameter,
        },
    )
