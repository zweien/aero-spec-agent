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
    if engine_count not in (1, 2, 3, 4):
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

    engine_position = "under_wing"
    pos_field = getattr(spec.engine, "position", None)
    if pos_field is not None and hasattr(pos_field, "value"):
        engine_position = str(pos_field.value).lower()

    x_offset = _engine_offset(spec, "x_offset")
    y_offset = _engine_offset(spec, "y_offset")
    z_offset = _engine_offset(spec, "z_offset")

    length = root_chord
    diameter = fuselage_diameter * 0.5

    if engine_count == 1:
        if engine_position == "nose":
            base_x = fuselage_length * 0.5
            base_y = 0.0
            base_z = 0.0
        elif engine_position == "tail":
            base_x = fuselage_length * 0.85
            base_y = 0.0
            base_z = fuselage_diameter * 0.2
        elif engine_position == "rear_fuselage":
            base_x = fuselage_length * 0.75
            base_y = 0.0
            base_z = fuselage_diameter * 0.5
        elif engine_position == "pusher":
            base_x = wing_x + root_chord * 0.75
            base_y = 0.0
            base_z = fuselage_diameter * 0.2
        else:
            base_x = wing_x + root_chord * 0.25
            base_y = 0.0
            base_z = wing_z - diameter * 0.6
        return [
            _create_engine_nacelle(
                adapter,
                name="center_engine",
                engine_count=engine_count,
                x_offset=x_offset,
                y_delta=y_offset,
                z_offset=z_offset,
                base_x=base_x,
                base_y=base_y,
                base_z=base_z,
                x_rel_location=base_x + x_offset,
                y_offset=y_offset,
                z_rel_location=base_z + z_offset,
                length=length,
                diameter=diameter,
            ),
        ]

    # Dual engine position overrides
    if engine_position == "wing_tip":
        base_x = wing_x + root_chord * 0.25
        base_y = wing_span * 0.48
        base_z = wing_z
    elif engine_position == "over_wing":
        base_x = wing_x + root_chord * 0.25
        base_y = wing_span * 0.25
        base_z = wing_z + diameter * 0.8
    else:
        base_x = wing_x + root_chord * 0.25
        base_y = wing_span * 0.25
        base_z = wing_z - diameter * 0.6

    if engine_count == 2:
        if engine_position == "push_pull":
            # Push-pull: front and rear engines on centerline
            front_x = fuselage_length * 0.15
            rear_x = fuselage_length * 0.85
            return [
                _create_engine_nacelle(
                    adapter,
                    name="front_engine",
                    engine_count=engine_count,
                    x_offset=x_offset,
                    y_delta=y_offset,
                    z_offset=z_offset,
                    base_x=front_x,
                    base_y=0.0,
                    base_z=0.0,
                    x_rel_location=front_x + x_offset,
                    y_offset=y_offset,
                    z_rel_location=z_offset,
                    length=length,
                    diameter=diameter,
                ),
                _create_engine_nacelle(
                    adapter,
                    name="rear_engine",
                    engine_count=engine_count,
                    x_offset=x_offset,
                    y_delta=y_offset,
                    z_offset=z_offset,
                    base_x=rear_x,
                    base_y=0.0,
                    base_z=0.0,
                    x_rel_location=rear_x + x_offset,
                    y_offset=y_offset,
                    z_rel_location=z_offset,
                    length=length,
                    diameter=diameter,
                ),
            ]
        return [
            _create_engine_nacelle(
                adapter,
                name="left_engine",
                engine_count=engine_count,
                x_offset=x_offset,
                y_delta=y_offset,
                z_offset=z_offset,
                base_x=base_x,
                base_y=base_y,
                base_z=base_z,
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
                x_offset=x_offset,
                y_delta=y_offset,
                z_offset=z_offset,
                base_x=base_x,
                base_y=base_y,
                base_z=base_z,
                x_rel_location=base_x + x_offset,
                y_offset=base_y + y_offset,
                z_rel_location=base_z + z_offset,
                length=length,
                diameter=diameter,
            ),
        ]

    # 3 engines: center + left/right symmetric
    if engine_count == 3:
        center_result = _create_engine_nacelle(
            adapter,
            name="center_engine",
            engine_count=engine_count,
            x_offset=x_offset,
            y_delta=y_offset,
            z_offset=z_offset,
            base_x=base_x,
            base_y=0.0,
            base_z=base_z,
            x_rel_location=base_x + x_offset,
            y_offset=y_offset,
            z_rel_location=base_z + z_offset,
            length=length,
            diameter=diameter,
        )
        left_result = _create_engine_nacelle(
            adapter,
            name="left_engine",
            engine_count=engine_count,
            x_offset=x_offset,
            y_delta=y_offset,
            z_offset=z_offset,
            base_x=base_x,
            base_y=base_y,
            base_z=base_z,
            x_rel_location=base_x + x_offset,
            y_offset=-(base_y + y_offset),
            z_rel_location=base_z + z_offset,
            length=length,
            diameter=diameter,
        )
        right_result = _create_engine_nacelle(
            adapter,
            name="right_engine",
            engine_count=engine_count,
            x_offset=x_offset,
            y_delta=y_offset,
            z_offset=z_offset,
            base_x=base_x,
            base_y=base_y,
            base_z=base_z,
            x_rel_location=base_x + x_offset,
            y_offset=base_y + y_offset,
            z_rel_location=base_z + z_offset,
            length=length,
            diameter=diameter,
        )
        return [center_result, left_result, right_result]

    # 4 engines: inner + outer pairs, symmetric
    inner_y = wing_span * 0.18
    outer_y = wing_span * 0.38
    return [
        _create_engine_nacelle(
            adapter,
            name="left_inner_engine",
            engine_count=engine_count,
            x_offset=x_offset,
            y_delta=y_offset,
            z_offset=z_offset,
            base_x=base_x,
            base_y=inner_y,
            base_z=base_z,
            x_rel_location=base_x + x_offset,
            y_offset=-(inner_y + y_offset),
            z_rel_location=base_z + z_offset,
            length=length,
            diameter=diameter,
        ),
        _create_engine_nacelle(
            adapter,
            name="left_outer_engine",
            engine_count=engine_count,
            x_offset=x_offset,
            y_delta=y_offset,
            z_offset=z_offset,
            base_x=base_x,
            base_y=outer_y,
            base_z=base_z,
            x_rel_location=base_x + x_offset,
            y_offset=-(outer_y + y_offset),
            z_rel_location=base_z + z_offset,
            length=length,
            diameter=diameter,
        ),
        _create_engine_nacelle(
            adapter,
            name="right_inner_engine",
            engine_count=engine_count,
            x_offset=x_offset,
            y_delta=y_offset,
            z_offset=z_offset,
            base_x=base_x,
            base_y=inner_y,
            base_z=base_z,
            x_rel_location=base_x + x_offset,
            y_offset=inner_y + y_offset,
            z_rel_location=base_z + z_offset,
            length=length,
            diameter=diameter,
        ),
        _create_engine_nacelle(
            adapter,
            name="right_outer_engine",
            engine_count=engine_count,
            x_offset=x_offset,
            y_delta=y_offset,
            z_offset=z_offset,
            base_x=base_x,
            base_y=outer_y,
            base_z=base_z,
            x_rel_location=base_x + x_offset,
            y_offset=outer_y + y_offset,
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
    x_offset: float = 0.0,
    y_delta: float = 0.0,
    z_offset: float = 0.0,
    base_x: float = 0.0,
    base_y: float = 0.0,
    base_z: float = 0.0,
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
            "engine.x_offset": x_offset,
            "engine.y_offset": y_delta,
            "engine.z_offset": z_offset,
            "base_x": base_x,
            "base_y": base_y,
            "base_z": base_z,
            "final_x": x_rel_location,
            "final_y": y_offset,
            "final_z": z_rel_location,
            "x_rel_location": x_rel_location,
            "y_offset": y_offset,
            "z_rel_location": z_rel_location,
            "length": length,
            "diameter": diameter,
            "fineness_ratio": fineness_ratio,
        },
    )
