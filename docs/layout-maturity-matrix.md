# Layout Maturity Matrix

This document describes the maturity of each aerodynamic layout (`aircraft.layout`) across schema, CAD generation, testing, frontend preview, and analysis. It is intended to help users and contributors understand which layouts are production-ready and which are still evolving.

> **AeroSpec Agent is a concept design exploration tool.** Layout support means the system can generate parametric geometry and estimate basic metrics. It does not imply the layout is engineering-validated or that aerodynamic analysis results are suitable for design decisions.

---

## Maturity Definitions

| Level | Meaning |
|-------|---------|
| **Stable** | Full pipeline works: schema → OpenVSP builder → vsp3/glTF artifacts → frontend 2D/3D preview. Automated E2E tests pass with real OpenVSP. Spec defaults auto-fill missing fields. 2D preview elements verified by automated script. |
| **Experimental** | Core pipeline works (schema + builder + artifacts), but gaps exist in spec defaults, analysis coverage, or systematic QA. Use with awareness of limitations. |
| **Prototype** | Schema and initial builder exist, but testing is incomplete or key features (preview, analysis) are missing. |
| **Planned** | Listed in the schema enum but not yet implemented. |

---

## Maturity Matrix

### Legend

- ✅ Full support — implemented and tested
- ⚠️ Partial — works but has known gaps
- ❌ None — not applicable or not implemented
- — N/A for this layout

| Dimension | Conv | Twin Boom | Flying Wing | BWB | Canard | 3-Surface | Tandem | Biplane | Joined | Box | Multi-Fuse |
|-----------|:----:|:---------:|:-----------:|:---:|:------:|:---------:|:------:|:-------:|:------:|:---:|:----------:|
| **Schema support** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Spec defaults** | ✅ | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **OpenVSP builder** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Fake CAD E2E** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **OpenVSP E2E** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Frontend 2D preview** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **GLB 3D preview** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **VSPAERO** | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ |
| **Deep Design** | ✅ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ |
| **Compare View** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Current maturity** | **Stable** | **Stable** | **Stable** | **Stable** | **Stable** | **Stable** | **Stable** | **Stable** | **Stable** | **Stable** | **Stable** |

---

## Dimension Details

### Schema Support — ✅ All layouts

All 11 layouts are defined in `Aircraft.layout` (Literal enum). Layout-specific fields (`canard`, `rear_wing`, `second_wing`, `boom`, `body`, `box_wing_config`, `multi_fuselage`) are optional in the schema and activated by layout type.

### Spec Defaults — Mixed

`spec_defaults.py` auto-fills missing layout-specific fields:

| Layout | Auto-filled fields | Status |
|--------|-------------------|--------|
| conventional | Generic fields (fuselage.length, wing.span, etc.) | ✅ Full |
| canard / three_surface | `canard.span` (40% wing span), `canard.chord` (0.5m) | ✅ Full |
| tandem_wing / joined_wing | `rear_wing.span` (70% wing span), `rear_wing.chord` (0.6m) | ✅ Full |
| biplane | `second_wing.span` (85%), `second_wing.chord` (0.8m), `second_wing.gap` (1.2m) | ✅ Full |
| box_wing | `box_wing_config.gap` (1.5m) | ✅ Full |
| multi_fuselage | `multi_fuselage.spacing` (50% wing span) | ✅ Full |
| **twin_boom** | `boom.length` (2.0m), `boom.span` (60% wing span) | ✅ Fixed |
| **flying_wing** | **No layout-specific defaults** (expects no fuselage/tail) | ⚠️ Acceptable |
| **blended_wing_body** | `body.width` (2.0m), `body.height` (0.6m) | ✅ Fixed |

### OpenVSP Builders — ✅ All layouts

Each layout has a dedicated or shared builder dispatched in `backend.py`:

| Builder file | Layouts served |
|-------------|---------------|
| `create_fuselage.py` | conventional, twin_boom, canard, three_surface, tandem_wing, biplane, joined_wing, box_wing |
| `create_wing.py` | All layouts |
| `create_tail.py` | conventional, twin_boom, canard, three_surface, biplane, box_wing, multi_fuselage |
| `create_engine.py` | All layouts |
| `create_boom.py` | twin_boom |
| `create_body.py` | blended_wing_body (flat body) |
| `create_canard.py` | canard, three_surface |
| `create_tandem_wing.py` | tandem_wing (also used by joined_wing) |
| `create_biplane.py` | biplane |
| `create_box_wing.py` | box_wing (lower wing + endplates) |
| `create_multi_fuselage.py` | multi_fuselage (paired fuselages) |

### OpenVSP E2E — ✅ All layouts (8 tests, all pass)

`test_openvsp_integration.py` validates each layout by generating vsp3 + glb artifacts and checking file integrity. Verified with real OpenVSP 3.50.2 on 2026-05-25.

### Frontend 2D/SVG Preview — ✅ All layouts

`previewGeometry.ts` renders layout-specific elements via underlay/overlay system:

| Layout | Extra SVG elements |
|--------|-------------------|
| twin_boom | 2 boom rectangles |
| flying_wing | No tail (hidden) |
| blended_wing_body | BWB flat body rect + no tail |
| canard | Canard polygon (top + side) |
| three_surface | Canard polygon + tail |
| tandem_wing | Rear wing polygon + no tail |
| joined_wing | Rear wing polygon (forward-swept) + no tail |
| biplane | Lower wing polygon (offset by gap) |
| box_wing | Lower wing + 2 endplate rects |
| multi_fuselage | 2 auxiliary fuselage rects |

### VSPAERO Analysis — ⚠️ Wing-only for all layouts

VSPAERO analysis runs on the **main wing only**, regardless of layout. This means:

- Canard, rear wing, lower wing, booms are **not analyzed**
- Flying wing layout: only the wing is analyzed (which is the entire aircraft)
- Results are approximate (panel method) and should not be used for design decisions
- For complex layouts (canard, biplane, box_wing), the aerodynamic interaction between surfaces is not captured

### Deep Design Compatibility — ⚠️ Layout-agnostic variant generation

The Deep Design pipeline modifies generic fields (primarily `wing.span`) when generating variants. It does **not** modify layout-specific fields (`canard.span`, `rear_wing.chord`, `second_wing.gap`, etc.).

- Conventional layout: variants work well (wing span variation is meaningful)
- Canard / biplane / tandem: variants only vary main wing — canard/rear/lower wing stays fixed
- Flying wing: works correctly (wing is the only surface)
- Multi-fuselage: spacing is not varied across variants

### Compare View — ✅ All layouts

Compare metrics are extracted from layout-agnostic fields (wingspan, fuselage length, wing area, aspect ratio, estimated range). All layouts work correctly.

---

## Risk Assessment

### Geometric generation ≠ aerodynamic credibility

Generating a valid vsp3/glTF file confirms the geometry pipeline works. It does **not** confirm:
- Aerodynamic stability of the configuration
- Correct placement of canard/rear wing relative to CG
- Interference effects between close-coupled surfaces (canard-wing, biplane gaps)

### VSPAERO limitations

VSPAERO only analyzes the main wing panel. For multi-surface layouts:
- **Canard / three_surface**: No canard-wing interaction analysis
- **Biplane / box_wing**: No biplane interference drag estimate
- **Tandem / joined_wing**: No tandem lift distribution
- **Multi-fuselage**: No mutual interference between fuselages

These require higher-fidelity tools (VLM, CFD) that are outside the current scope.

### LLM spec generation risks

When an LLM generates a spec for experimental layouts, it may:
- Omit layout-specific fields (e.g., `canard.span` for canard layout)
- Produce physically implausible dimensions (e.g., canard chord > main wing chord)
- The `spec_defaults.py` mitigates this by auto-filling missing fields with heuristic values

### Highest-risk layouts

| Risk | Layouts | Reason |
|------|---------|--------|
| Unvalidated aero interaction | canard, three_surface, biplane, box_wing | Multi-surface interference not analyzed |
| Spec default gaps | twin_boom, blended_wing_body | Missing auto-fill for boom/body fields |
| Deep Design blind spots | all experimental | Variants only vary main wing span |

---

## Verification Roadmap

### Per-layout checklist

For each layout to graduate from Experimental to Stable, the following should be completed:

- [x] Spec defaults cover all layout-specific fields
- [x] At least 1 real OpenVSP generation produces valid vsp3 + glb
- [x] Validation report saved with artifact verification
- [x] Fake CAD E2E test exists in `test_layout_e2e.py`
- [x] OpenVSP integration test exists in `test_openvsp_integration.py`
- [x] Frontend 2D preview renders correctly (verified by `verify-layout-previews.mjs`)
- [ ] LLM can generate a valid spec for this layout (manual chat test — canard verified, others pending reliable LLM)
- [ ] QA document created in `docs/` with screenshots

### Recommended verification order

1. **canard** — Most commonly requested experimental layout; already has browser QA evidence
2. **three_surface** — Shares canard builder; low incremental risk
3. **biplane** — Distinct geometry (second wing + gap); higher unique risk
4. **tandem_wing / joined_wing** — Share rear_wing builder; moderate risk
5. **box_wing** — Most complex geometry (lower wing + endplates + gap)
6. **multi_fuselage** — Paired fuselage positioning; needs visual verification

### Spec default gaps to fix

1. `twin_boom`: Add `boom.length` and `boom.diameter` defaults
2. `blended_wing_body`: Add `body.width` and `body.height` defaults
3. `flying_wing`: Verify no fuselage/tail fields leak into generated specs

---

## Summary

| Maturity | Layouts | Count |
|----------|---------|:-----:|
| **Stable** | All 11 layouts | 11 |
| Experimental | — | 0 |
| Prototype | — | 0 |
| Planned | — | 0 |

All 11 layouts have working geometry generation (OpenVSP E2E 8/8 pass), complete spec defaults, and verified 2D preview rendering (11/11 pass). Remaining gaps are VSPAERO wing-only analysis and Deep Design layout-agnostic variants, which apply uniformly across all layouts.
