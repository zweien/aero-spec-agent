"""LayoutPlan — single source of truth for per-layout geometry knowledge.

Each of the 11 layouts declares how it differs from a conventional baseline:
which extra spec sections it needs, which extra lifting surfaces enter aero
analysis, whether it has a tail, and how its fuselage is built. Three consumers
previously each kept their own copy of this knowledge:

  - backend.py OpenVspBackend.generate (imperative if/elif dispatch)
  - spec_defaults.py _layout_aware_defaults (which sections to default-fill)
  - vspaero_analysis.py LAYOUT_ANALYSIS_NAMES (which surfaces to analyze)

Adding a layout meant editing 3-4 places that could silently drift. They now
all read from LAYOUT_PLANS below.

What stays out of this table (legitimately separate concerns):
  - spec-default scalar math (span*0.4 etc.) — lives in spec_defaults.py,
    keyed by the section names declared here.
  - builder return-type normalization (create_main_wing returns a Union) —
    stays as code in backend.py.
  - frontend SVG preview (previewGeometry.ts) — different language/domain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

FuselageMode = Literal["standard", "flat_body", "multi_fuselage", "none"]


@dataclass(frozen=True)
class LayoutPlan:
    """How a layout differs from the conventional baseline."""

    # Extra spec sections this layout requires (beyond fuselage/wing/tail/engine).
    # spec_defaults._layout_aware_defaults reads this to know which sections to
    # default-fill when the LLM omits them.
    extra_sections: tuple[str, ...] = ()
    # Extra lifting-surface component names that enter VSPAERO analysis beyond
    # main_wing. Non-lifting extras (booms, body) are intentionally absent —
    # they are built but not analyzed.
    extra_analysis_surfaces: tuple[str, ...] = ()
    # Conventional has a tail; flying_wing / BWB / tandem / joined do not.
    skip_tail: bool = False
    # How the center body is built. "none" = flying_wing (no fuselage at all).
    fuselage_mode: FuselageMode = "standard"


# The 11 layouts. conventional is the implicit baseline (all defaults).
LAYOUT_PLANS: dict[str, LayoutPlan] = {
    "conventional": LayoutPlan(),
    "twin_boom": LayoutPlan(
        extra_sections=("boom",),
    ),
    "flying_wing": LayoutPlan(
        skip_tail=True,
        fuselage_mode="none",
    ),
    "blended_wing_body": LayoutPlan(
        extra_sections=("body",),
        skip_tail=True,
        fuselage_mode="flat_body",
    ),
    "canard": LayoutPlan(
        extra_sections=("canard",),
        extra_analysis_surfaces=("canard",),
    ),
    "three_surface": LayoutPlan(
        extra_sections=("canard",),
        extra_analysis_surfaces=("canard",),
    ),
    "tandem_wing": LayoutPlan(
        extra_sections=("rear_wing",),
        extra_analysis_surfaces=("rear_wing",),
        skip_tail=True,
    ),
    "biplane": LayoutPlan(
        extra_sections=("second_wing",),
        extra_analysis_surfaces=("lower_wing",),
    ),
    "joined_wing": LayoutPlan(
        extra_sections=("rear_wing",),
        extra_analysis_surfaces=("rear_wing",),
        skip_tail=True,
    ),
    "box_wing": LayoutPlan(
        extra_sections=("box_wing_config",),
        extra_analysis_surfaces=("box_lower_wing",),
    ),
    "multi_fuselage": LayoutPlan(
        extra_sections=("multi_fuselage",),
        fuselage_mode="multi_fuselage",
    ),
}


def get_layout_plan(layout: str) -> LayoutPlan:
    """Return the plan for a layout (case-insensitive), defaulting to conventional."""
    return LAYOUT_PLANS.get(str(layout).lower().strip(), LAYOUT_PLANS["conventional"])
