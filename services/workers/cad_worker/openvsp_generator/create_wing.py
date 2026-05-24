from __future__ import annotations

from typing import Any, Union

from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult


def _value(scalar: Any, default: float | None = None) -> float:
    if scalar is None:
        if default is None:
            raise ValueError("missing required scalar")
        return default
    return float(scalar.value)


def _wing_z_location(position: str, fuselage_diameter: float) -> float:
    factors = {
        "high": 0.45,
        "mid": 0.0,
        "low": -0.45,
    }
    return factors.get(position, 0.0) * fuselage_diameter


def _get_num_sections(spec: Any) -> int:
    """Return number of wing sections (1 if not specified or invalid)."""
    sections_attr = getattr(spec.wing, "sections", None)
    if sections_attr is None:
        return 1
    try:
        val = int(sections_attr.value)
        return val if val >= 1 else 1
    except (AttributeError, ValueError, TypeError):
        return 1


def _get_planform(spec: Any) -> str | None:
    """Return wing planform type if specified."""
    planform_attr = getattr(spec.wing, "planform", None)
    if planform_attr is None:
        return None
    try:
        return str(planform_attr.value).lower()
    except (AttributeError, ValueError, TypeError):
        return None


def _apply_planform_constraints(
    planform: str | None, sweep: float, tip_chord: float, root_chord: float,
) -> tuple[float, float]:
    """Apply geometric constraints for special planform types."""
    if planform == "delta":
        sweep = max(sweep, 50.0)
        tip_chord = min(tip_chord, root_chord * 0.2)
    elif planform == "ogee":
        sweep = max(sweep, 45.0)
        tip_chord = min(tip_chord, root_chord * 0.25)
    return sweep, tip_chord


def _create_single_section(adapter: Any, spec: Any) -> GeometryBuildResult:
    """Create a single-section wing (original behavior)."""
    geom_id = adapter.add_geom("WING")
    span = _value(spec.wing.span)
    root_chord = _value(spec.wing.root_chord)
    tip_chord = _value(spec.wing.tip_chord)
    sweep = _value(spec.wing.sweep, 0.0)
    dihedral = _value(spec.wing.dihedral, 0.0)
    planform = _get_planform(spec)
    sweep, tip_chord = _apply_planform_constraints(planform, sweep, tip_chord, root_chord)
    fuselage_length = _value(spec.fuselage.length)
    fuselage_diameter = _value(spec.fuselage.max_diameter, 0.75)
    position = str(spec.wing.position.value).lower()
    x_rel_location = fuselage_length * 0.40
    z_rel_location = _wing_z_location(position, fuselage_diameter)

    adapter.set_param(geom_id, "TotalSpan", "WingGeom", span)
    adapter.set_param(geom_id, "Root_Chord", "XSec_1", root_chord)
    adapter.set_param(geom_id, "Tip_Chord", "XSec_1", tip_chord)
    adapter.set_param(geom_id, "Sweep", "XSec_1", sweep)
    adapter.set_param(geom_id, "Dihedral", "XSec_1", dihedral)
    adapter.set_param(geom_id, "X_Rel_Location", "XForm", x_rel_location)
    adapter.set_param(geom_id, "Z_Rel_Location", "XForm", z_rel_location)

    return GeometryBuildResult(
        name="main_wing",
        geom_id=geom_id,
        applied_parameters={
            "span": span,
            "root_chord": root_chord,
            "tip_chord": tip_chord,
            "sweep": sweep,
            "dihedral": dihedral,
            "x_rel_location": x_rel_location,
            "z_rel_location": z_rel_location,
        },
    )


def _create_multi_section_wing(
    adapter: Any, spec: Any, num_sections: int
) -> list[GeometryBuildResult]:
    """Create a multi-section wing with independent WING geometries."""
    total_span = _value(spec.wing.span)
    root_chord = _value(spec.wing.root_chord)
    tip_chord = _value(spec.wing.tip_chord)
    sweep = _value(spec.wing.sweep, 0.0)
    dihedral = _value(spec.wing.dihedral, 0.0)
    planform = _get_planform(spec)
    sweep, tip_chord = _apply_planform_constraints(planform, sweep, tip_chord, root_chord)
    fuselage_length = _value(spec.fuselage.length)
    fuselage_diameter = _value(spec.fuselage.max_diameter, 0.75)
    position = str(spec.wing.position.value).lower()

    inner_sweep = _value(spec.wing.inner_sweep, sweep)
    inner_dihedral = _value(spec.wing.inner_dihedral, dihedral)

    x_rel_location = fuselage_length * 0.40
    z_rel_location = _wing_z_location(position, fuselage_diameter)

    section_span = total_span / num_sections

    results: list[GeometryBuildResult] = []
    y_offset = 0.0

    section_names = {1: "main_wing", 2: ["inner_wing", "outer_wing"]}
    if num_sections == 2:
        names = section_names[2]
    elif num_sections == 3:
        names = ["inner_wing", "mid_wing", "outer_wing"]
    else:
        names = [f"wing_section_{i + 1}" for i in range(num_sections)]

    for i in range(num_sections):
        geom_id = adapter.add_geom("WING")

        # Linear interpolation of chords
        sec_root_chord = root_chord + i * (tip_chord - root_chord) / num_sections
        sec_tip_chord = root_chord + (i + 1) * (tip_chord - root_chord) / num_sections

        # First section uses spec sweep/dihedral, rest use inner_sweep/inner_dihedral
        if i == 0:
            sec_sweep = sweep
            sec_dihedral = dihedral
        else:
            sec_sweep = inner_sweep
            sec_dihedral = inner_dihedral

        adapter.set_param(geom_id, "TotalSpan", "WingGeom", section_span)
        adapter.set_param(geom_id, "Root_Chord", "XSec_1", sec_root_chord)
        adapter.set_param(geom_id, "Tip_Chord", "XSec_1", sec_tip_chord)
        adapter.set_param(geom_id, "Sweep", "XSec_1", sec_sweep)
        adapter.set_param(geom_id, "Dihedral", "XSec_1", sec_dihedral)
        adapter.set_param(geom_id, "X_Rel_Location", "XForm", x_rel_location)
        adapter.set_param(geom_id, "Z_Rel_Location", "XForm", z_rel_location)
        adapter.set_param(geom_id, "Y_Rel_Location", "XForm", y_offset)

        results.append(
            GeometryBuildResult(
                name=names[i],
                geom_id=geom_id,
                applied_parameters={
                    "span": section_span,
                    "root_chord": sec_root_chord,
                    "tip_chord": sec_tip_chord,
                    "sweep": sec_sweep,
                    "dihedral": sec_dihedral,
                    "x_rel_location": x_rel_location,
                    "z_rel_location": z_rel_location,
                    "y_rel_location": y_offset,
                    "section_index": i,
                },
            )
        )
        y_offset += section_span

    return results


def create_main_wing(
    adapter: Any, spec: Any
) -> Union[GeometryBuildResult, list[GeometryBuildResult]]:
    """Create the main wing geometry.

    Returns a single GeometryBuildResult for single-section wings,
    or a list of GeometryBuildResult for multi-section wings (sections >= 2).
    """
    num_sections = _get_num_sections(spec)
    if num_sections <= 1:
        return _create_single_section(adapter, spec)
    return _create_multi_section_wing(adapter, spec, num_sections)
