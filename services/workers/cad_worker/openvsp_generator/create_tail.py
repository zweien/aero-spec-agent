from typing import Any

from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult


def create_tail(adapter: Any, spec: Any) -> list[GeometryBuildResult]:
    wing_span = float(spec.wing.span.value)
    root_chord = float(spec.wing.root_chord.value)
    tail_x = float(spec.fuselage.length.value) * 0.42

    horizontal_tail = _create_tail_surface(
        adapter,
        name="horizontal_tail",
        span=wing_span * 0.28,
        chord=root_chord * 0.45,
        x_rel_location=tail_x,
    )
    vertical_tail = _create_tail_surface(
        adapter,
        name="vertical_tail",
        span=wing_span * 0.16,
        chord=root_chord * 0.55,
        x_rel_location=tail_x,
    )

    return [horizontal_tail, vertical_tail]


def _create_tail_surface(
    adapter: Any,
    *,
    name: str,
    span: float,
    chord: float,
    x_rel_location: float,
) -> GeometryBuildResult:
    geom_id = adapter.add_geom("WING")

    adapter.set_param(geom_id, "TotalSpan", "WingGeom", span)
    adapter.set_param(geom_id, "Root_Chord", "XSec_1", chord)
    adapter.set_param(geom_id, "Tip_Chord", "XSec_1", chord)
    adapter.set_param(geom_id, "X_Rel_Location", "XForm", x_rel_location)

    return GeometryBuildResult(
        name=name,
        geom_id=geom_id,
        applied_parameters={
            "span": span,
            "chord": chord,
            "x_rel_location": x_rel_location,
        },
    )
