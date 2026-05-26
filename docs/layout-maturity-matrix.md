# Layout Maturity Matrix

This document describes the verification status of each aerodynamic layout (`aircraft.layout`) across multiple dimensions: schema, CAD generation, testing, frontend preview, and analysis.

> **Stable means the software pipeline can generate artifacts reliably.** It does not mean the aircraft configuration is aerodynamically optimal, structurally feasible, or engineering certified. All layouts are for concept design exploration only.

---

## Verification Dimensions

| Dimension | Meaning |
|-----------|---------|
| **Pipeline Stable** | Schema, defaults, builder, fake pipeline, and basic artifact generation pass. |
| **OpenVSP Verified** | Real OpenVSP 3.50.2 backend has generated vsp3/glb/step/obj artifacts with non-zero file sizes. |
| **Visually Checked** | A human has viewed the 3D model and confirmed no obvious misalignment, missing parts, or scale anomalies. |
| **Aero Approximate** | VSPAERO panel method analysis available. Results are approximate and for concept-stage comparison only, not engineering decisions. |
| **Engineering Validated** | Higher-fidelity analysis (VLM, CFD, structural) confirmed. **Currently none.** |

---

## Maturity Matrix

### Legend

- ✅ Verified — implemented, tested, and confirmed
- ⚠️ Partial — works but has known gaps
- ❌ None — not applicable or not implemented
- — N/A for this layout

| Dimension | Conv | Twin Boom | Flying Wing | BWB | Canard | 3-Surface | Tandem | Biplane | Joined | Box | Multi-Fuse |
|-----------|:----:|:---------:|:-----------:|:---:|:------:|:---------:|:------:|:-------:|:------:|:---:|:----------:|
| **Pipeline Stable** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Real OpenVSP Verified** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Frontend 2D preview** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **GLB 3D preview** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Visually Checked** | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| **VSPAERO (approximate)** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Deep Design** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Compare View** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Engineering Validated** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

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

### VSPAERO Analysis — ✅ All layouts (multi-surface)

VSPAERO analysis includes **all aerodynamic surfaces** based on layout via `build_analysis_geoms()`:

| Layout | Surfaces analyzed |
|--------|------------------|
| conventional, twin_boom, flying_wing, blended_wing_body, multi_fuselage | main_wing only |
| canard, three_surface | main_wing + canard |
| tandem_wing, joined_wing | main_wing + rear_wing |
| biplane | main_wing + lower_wing |
| box_wing | main_wing + box_lower_wing |

Results reflect combined multi-surface aerodynamics. `VspaeroReport.components_analyzed` lists which surfaces were included. Results are approximate (panel method) and should not be used for design decisions.

### Deep Design Compatibility — ✅ All layouts (layout-aware strategies)

The Deep Design pipeline varies layout-specific fields via `LAYOUT_STRATEGIES`:

| Layout | Fields varied |
|--------|--------------|
| conventional, twin_boom, flying_wing, blended_wing_body, multi_fuselage | wing.span ±2m |
| canard, three_surface | wing.span ±2m, canard.span ±0.5m |
| tandem_wing, joined_wing | wing.span ±2m, rear_wing.span ±1m |
| biplane | wing.span ±2m, second_wing.gap ±0.2m |
| box_wing | wing.span ±2m, box_wing_config.gap ±0.3m |

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

VSPAERO now analyzes all aerodynamic surfaces per layout. Remaining limitations:
- Panel method is inherently approximate — results should not be used for design decisions
- Per-surface aerodynamic reports are not available (VSPAERO outputs combined metrics only)
- Non-wing geometries (fuselage, booms, body) are not included in analysis

Higher-fidelity tools (VLM, CFD) remain outside the current scope.

### LLM spec generation risks

When an LLM generates a spec for experimental layouts, it may:
- Omit layout-specific fields (e.g., `canard.span` for canard layout)
- Produce physically implausible dimensions (e.g., canard chord > main wing chord)
- The `spec_defaults.py` mitigates this by auto-filling missing fields with heuristic values

### Highest-risk layouts

| Risk | Layouts | Reason |
|------|---------|--------|
| Unvalidated aero interaction | canard, three_surface, biplane, box_wing | Multi-surface interference captured but approximate |
| Spec default gaps | — | All gaps fixed |
| Deep Design blind spots | — | All layouts now have layout-aware strategies |

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

1. ~~`twin_boom`: Add `boom.length` and `boom.diameter` defaults~~ ✅ Fixed
2. ~~`blended_wing_body`: Add `body.width` and `body.height` defaults~~ ✅ Fixed
3. `flying_wing`: Verify no fuselage/tail fields leak into generated specs

---

## QA Reports

- Fake pipeline QA: [docs/layout-openvsp-qa.md](layout-openvsp-qa.md) — validates software pipeline structure
- Real OpenVSP QA: [docs/layout-openvsp-real-qa.md](layout-openvsp-real-qa.md) — validates real geometry generation
- Visual QA: [docs/layout-visual-qa.md](layout-visual-qa.md) — human visual inspection of 3D models

---

## Summary

| Verification | Layouts | Count |
|-------------|---------|:-----:|
| **Pipeline Stable** | All 11 layouts | 11 |
| **Real OpenVSP Verified** | All 11 layouts | 11 |
| **Visually Checked** | Pending | 0 |
| **Engineering Validated** | None | 0 |

All 11 layouts have pipeline-stable geometry generation (fake + real OpenVSP QA 11/11 pass), complete spec defaults, verified 2D preview rendering (11/11 pass), multi-surface VSPAERO analysis, and layout-aware Deep Design variant strategies. **No layout has been engineering-validated.** Visual inspection of 3D models is recommended before relying on generated geometry.
