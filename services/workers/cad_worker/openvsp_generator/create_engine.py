from typing import Any

from services.workers.cad_worker.openvsp_generator.errors import (
    CadGenerationError,
    UnsupportedGeometryError,
)
from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult


def _wing_z(position: str, fuselage_diameter: float) -> float:
    factors = {"high": 0.45, "mid": 0.0, "low": -0.45}
    return factors.get(position, 0.0) * fuselage_diameter


def _engine_offset(spec: Any, attr: str) -> float:
    field = getattr(spec.engine, attr, None)
    if field is not None and hasattr(field, "value"):
        return float(field.value)
    return 0.0


def create_engine_nacelles(adapter: Any, spec: Any) -> list[GeometryBuildResult]:
    engine_count = int(spec.engine.count.value)
    if engine_count not in (1, 2):
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
    fuselage_length = float(spec.fuselage.length.value)
    wing_x = fuselage_length * 0.40
    wing_position = str(spec.wing.position.value).lower()
    wing_z = _wing_z(wing_position, fuselage_diameter)

    x_offset = _engine_offset(spec, "x_offset")
    y_offset = _engine_offset(spec, "y_offset")
    z_offset = _engine_offset(spec, "z_offset")

    length = root_chord
    diameter = fuselage_diameter * 0.5

    if engine_count == 1:
        engine_position = (
            spec.engine.position.value if spec.engine.position else "nose"
        )
        if engine_position == "nose":
            base_x = fuselage_length * 0.5
            base_z = 0.0
        elif engine_position == "tail":
            base_x = fuselage_length * 0.85
            base_z = fuselage_diameter * 0.2
        else:
            base_x = wing_x + root_chord * 0.25
            base_z = wing_z - diameter * 0.6
        return [
            _create_engine_nacelle(
                adapter,
                name="center_engine",
                engine_count=engine_count,
                x_rel_location=base_x + x_offset,
                y_offset=y_offset,
                z_rel_location=base_z + z_offset,
                length=length,
                diameter=diameter,
            ),
        ]

    base_x = wing_x + root_chord * 0.25
    base_y = wing_span * 0.25
    base_z = wing_z - diameter * 0.6

    return [
        _create_engine_nacelle(
            adapter,
            name="left_engine",
            engine_count=engine_count,
            x_rel_location=base_x + x_offset,
            y_offset=-(base_y + y_offset),
            z_rel_location=base_z + z_offset,
            length=length,
            diameter=diameter,
        ),
        _create_engine_nacelle(
            adapter,
            name="right_engine",
            engine_count=engine_count,
            x_rel_location=base_x + x_offset,
            y_offset=base_y + y_offset,
            z_rel_location=base_z + z_offset,
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
    y_offset: float,
    z_rel_location: float,
    length: float,
    diameter: float,
) -> GeometryBuildResult:
    geom_id = adapter.add_geom("POD")
    if diameter <= 0:
        raise CadGenerationError("Engine nacelle diameter must be positive")
    fineness_ratio = length / (diameter / 2.0)

    adapter.set_param(geom_id, "X_Rel_Location", "XForm", x_rel_location)
    adapter.set_param(geom_id, "Y_Rel_Location", "XForm", y_offset)
    adapter.set_param(geom_id, "Z_Rel_Location", "XForm", z_rel_location)
    adapter.set_param(geom_id, "Length", "Design", length)
    adapter.set_param(geom_id, "FineRatio", "Design", fineness_ratio)

    return GeometryBuildResult(
        name=name,
        geom_id=geom_id,
        applied_parameters={
            "engine.count": engine_count,
            "x_rel_location": x_rel_location,
            "y_offset": y_offset,
            "z_rel_location": z_rel_location,
            "length": length,
            "diameter": diameter,
            "fineness_ratio": fineness_ratio,
        },
    )
