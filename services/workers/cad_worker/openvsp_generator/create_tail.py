from typing import Any

from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult


def create_tail(adapter: Any, spec: Any) -> list[GeometryBuildResult]:
    wing_span = float(spec.wing.span.value)
    root_chord = float(spec.wing.root_chord.value)
    tail_x = float(spec.fuselage.length.value) * 0.90

    tail_type = "conventional"
    if hasattr(spec, "tail") and spec.tail is not None and hasattr(spec.tail, "type"):
        tail_type = str(spec.tail.type.value).lower() if spec.tail.type else "conventional"

    v_tail_span = wing_span * 0.16
    h_tail_span = wing_span * 0.28

    if tail_type == "t_tail":
        return _create_t_tail(adapter, tail_x, h_tail_span, v_tail_span, root_chord)

    if tail_type == "v_tail":
        return _create_v_tail(adapter, tail_x, h_tail_span, root_chord)

    if tail_type == "inverted_v":
        return _create_inverted_v(adapter, tail_x, h_tail_span, root_chord)

    if tail_type == "cruciform":
        return _create_cruciform(adapter, tail_x, h_tail_span, v_tail_span, root_chord)

    # Default: conventional
    horizontal_tail = _create_tail_surface(
        adapter,
        name="horizontal_tail",
        span=h_tail_span,
        chord=root_chord * 0.45,
        x_rel_location=tail_x,
    )
    vertical_tail = _create_tail_surface(
        adapter,
        name="vertical_tail",
        span=v_tail_span,
        chord=root_chord * 0.55,
        x_rel_location=tail_x,
        x_rel_rotation=90.0,
    )
    return [horizontal_tail, vertical_tail]


def _create_t_tail(
    adapter: Any,
    tail_x: float,
    h_tail_span: float,
    v_tail_span: float,
    root_chord: float,
) -> list[GeometryBuildResult]:
    # T-tail: taller vertical tail, horizontal tail on top
    vertical_tail = _create_tail_surface(
        adapter,
        name="vertical_tail",
        span=v_tail_span * 1.2,
        chord=root_chord * 0.55,
        x_rel_location=tail_x,
        x_rel_rotation=90.0,
    )
    horizontal_tail = _create_tail_surface(
        adapter,
        name="horizontal_tail",
        span=h_tail_span,
        chord=root_chord * 0.45,
        x_rel_location=tail_x,
        z_rel_location=v_tail_span * 1.2,
    )
    return [vertical_tail, horizontal_tail]


def _create_tail_surface(
    adapter: Any,
    *,
    name: str,
    span: float,
    chord: float,
    x_rel_location: float,
    x_rel_rotation: float | None = None,
    z_rel_location: float | None = None,
) -> GeometryBuildResult:
    geom_id = adapter.add_geom("WING")

    adapter.set_param(geom_id, "TotalSpan", "WingGeom", span)
    adapter.set_param(geom_id, "Root_Chord", "XSec_1", chord)
    adapter.set_param(geom_id, "Tip_Chord", "XSec_1", chord)
    adapter.set_param(geom_id, "X_Rel_Location", "XForm", x_rel_location)
    if x_rel_rotation is not None:
        adapter.set_param(geom_id, "X_Rel_Rotation", "XForm", x_rel_rotation)
    if z_rel_location is not None:
        adapter.set_param(geom_id, "Z_Rel_Location", "XForm", z_rel_location)

    applied_parameters: dict[str, object] = {
        "span": span,
        "chord": chord,
        "x_rel_location": x_rel_location,
    }
    if x_rel_rotation is not None:
        applied_parameters["x_rel_rotation"] = x_rel_rotation
    if z_rel_location is not None:
        applied_parameters["z_rel_location"] = z_rel_location

    return GeometryBuildResult(
        name=name,
        geom_id=geom_id,
        applied_parameters=applied_parameters,
    )


def _create_v_tail(
    adapter: Any,
    tail_x: float,
    h_tail_span: float,
    root_chord: float,
) -> list[GeometryBuildResult]:
    v_tail_chord = root_chord * 0.50
    v_tail_span = h_tail_span * 0.85
    result = _create_tail_surface(
        adapter,
        name="v_tail",
        span=v_tail_span,
        chord=v_tail_chord,
        x_rel_location=tail_x,
        x_rel_rotation=45.0,
    )
    return [result]


def _create_inverted_v(
    adapter: Any,
    tail_x: float,
    h_tail_span: float,
    root_chord: float,
) -> list[GeometryBuildResult]:
    v_tail_chord = root_chord * 0.50
    v_tail_span = h_tail_span * 0.85
    result = _create_tail_surface(
        adapter,
        name="inverted_v_tail",
        span=v_tail_span,
        chord=v_tail_chord,
        x_rel_location=tail_x,
        x_rel_rotation=-45.0,
    )
    return [result]


def _create_cruciform(
    adapter: Any,
    tail_x: float,
    h_tail_span: float,
    v_tail_span: float,
    root_chord: float,
) -> list[GeometryBuildResult]:
    vertical_tail = _create_tail_surface(
        adapter,
        name="vertical_tail",
        span=v_tail_span,
        chord=root_chord * 0.55,
        x_rel_location=tail_x,
        x_rel_rotation=90.0,
    )
    cruciform_htail = _create_tail_surface(
        adapter,
        name="cruciform_htail",
        span=h_tail_span * 0.90,
        chord=root_chord * 0.42,
        x_rel_location=tail_x,
        z_rel_location=v_tail_span * 0.50,
    )
    return [vertical_tail, cruciform_htail]
