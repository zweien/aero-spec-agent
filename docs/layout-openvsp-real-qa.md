---
qa_id: layout-openvsp-qa
status: pass
date: 2026-05-26
env: openvsp
openvsp_version: "OpenVSP 3.50.2"
backend: openvsp
layouts_total: 11
layouts_pass: 11
layouts_skip: 0
layouts_fail: 0
---

# Layout OpenVSP QA Report

> **Note:** This report validates the software generation pipeline. "PASS" means artifacts were generated successfully. It does NOT mean the aircraft configuration is aerodynamically optimal, structurally feasible, or engineering certified.

> **Confirmed:** Real OpenVSP artifacts generated. Visual inspection of 3D models recommended for geometric plausibility.

**Date:** 2026-05-26
**Backend:** openvsp
**OpenVSP:** OpenVSP 3.50.2
**Result:** 11/11 layouts passed

## Environment

| Item | Value |
|------|-------|
| Date | 2026-05-26 |
| Backend | openvsp |
| OpenVSP | OpenVSP 3.50.2 |
| Python | 3.12.3 |
| Total layouts | 11 |
| Passed | 11 |
| Skipped | 0 |
| Failed | 0 |
| Script | `scripts/validate_layout_matrix.py` |

## Layout Verification Matrix

| Layout | Spec | Defaults | VSP3 | GLB | STEP | OBJ | Log | Report | Metrics | Backend | Status |
|--------|:----:|:--------:|:----:|:---:|:----:|:---:|:---:|:------:|:-------:|:-------:|:------:|
| conventional | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ openvsp | ✅ |
| twin_boom | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ openvsp | ✅ |
| flying_wing | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ openvsp | ✅ |
| blended_wing_body | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ openvsp | ✅ |
| canard | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ openvsp | ✅ |
| three_surface | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ openvsp | ✅ |
| tandem_wing | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ openvsp | ✅ |
| biplane | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ openvsp | ✅ |
| joined_wing | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ openvsp | ✅ |
| box_wing | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ openvsp | ✅ |
| multi_fuselage | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ openvsp | ✅ |

## Per-Layout Details

### conventional

- **Status:** PASS
- **YAML:** `packages/aircraft-schema/examples/twin_engine_uav.yaml`
- **Backend:** openvsp
- **Components:** fuselage, main_wing, horizontal_tail, vertical_tail, left_engine, right_engine
- **Visual Inspection:** Optional

| Artifact | Status | Size |
|----------|--------|------|
| aircraft.vsp3 | pass | 256.5 KB |
| aircraft.glb | pass | 68.5 KB |
| aircraft.step | pass | 606.9 KB |
| aircraft.obj | pass | 150.9 KB |
| aircraft_spec.yaml | pass | 2.6 KB |
| generation_log.json | pass | 5.2 KB |
| validation_report.json | pass | 15.5 KB |

**VSPAERO Analysis:** VSPAERO not run for this layout (triggered separately via settings)

- **Frontend 2D preview:** ✅ (verified by `verify-layout-previews.mjs`)

### twin_boom

- **Status:** PASS
- **YAML:** `packages/aircraft-schema/examples/twin_boom_pusher_uav.yaml`
- **Backend:** openvsp
- **Components:** fuselage, main_wing, left_boom, right_boom, horizontal_tail, vertical_tail, center_engine
- **Visual Inspection:** Optional

| Artifact | Status | Size |
|----------|--------|------|
| aircraft.vsp3 | pass | 428.6 KB |
| aircraft.glb | pass | 85.1 KB |
| aircraft.step | pass | 653.4 KB |
| aircraft.obj | pass | 191.1 KB |
| aircraft_spec.yaml | pass | 2.2 KB |
| generation_log.json | pass | 4.9 KB |
| validation_report.json | pass | 14.6 KB |

**VSPAERO Analysis:** VSPAERO not run for this layout (triggered separately via settings)

- **Frontend 2D preview:** ✅ (verified by `verify-layout-previews.mjs`)

### flying_wing

- **Status:** PASS
- **YAML:** `packages/aircraft-schema/examples/flying_wing_uav.yaml`
- **Backend:** openvsp
- **Components:** inner_wing, outer_wing, center_engine
- **Visual Inspection:** Optional

| Artifact | Status | Size |
|----------|--------|------|
| aircraft.vsp3 | pass | 125.5 KB |
| aircraft.glb | pass | 40.8 KB |
| aircraft.step | pass | 390.7 KB |
| aircraft.obj | pass | 90.5 KB |
| aircraft_spec.yaml | pass | 2.2 KB |
| generation_log.json | pass | 3.2 KB |
| validation_report.json | pass | 14.8 KB |

**VSPAERO Analysis:** VSPAERO not run for this layout (triggered separately via settings)

- **Frontend 2D preview:** ✅ (verified by `verify-layout-previews.mjs`)

### blended_wing_body

- **Status:** PASS
- **YAML:** `packages/aircraft-schema/examples/bwb_uav.yaml`
- **Backend:** openvsp
- **Components:** flat_body, inner_wing, outer_wing, left_engine, right_engine
- **Visual Inspection:** Optional

| Artifact | Status | Size |
|----------|--------|------|
| aircraft.vsp3 | pass | 223.5 KB |
| aircraft.glb | pass | 56.3 KB |
| aircraft.step | pass | 427.4 KB |
| aircraft.obj | pass | 128.1 KB |
| aircraft_spec.yaml | pass | 2.4 KB |
| generation_log.json | pass | 4.5 KB |
| validation_report.json | pass | 15.2 KB |

**VSPAERO Analysis:** VSPAERO not run for this layout (triggered separately via settings)

- **Frontend 2D preview:** ✅ (verified by `verify-layout-previews.mjs`)

### canard

- **Status:** PASS
- **YAML:** `packages/aircraft-schema/examples/canard_uav.yaml`
- **Backend:** openvsp
- **Components:** fuselage, main_wing, canard, horizontal_tail, vertical_tail, center_engine
- **Visual Inspection:** Recommended (complex layout)

| Artifact | Status | Size |
|----------|--------|------|
| aircraft.vsp3 | pass | 281.6 KB |
| aircraft.glb | pass | 79.2 KB |
| aircraft.step | pass | 781.5 KB |
| aircraft.obj | pass | 176.7 KB |
| aircraft_spec.yaml | pass | 2.4 KB |
| generation_log.json | pass | 4.3 KB |
| validation_report.json | pass | 15.1 KB |

**VSPAERO Analysis:** VSPAERO not run for this layout (triggered separately via settings)

- **Frontend 2D preview:** ✅ (verified by `verify-layout-previews.mjs`)

### three_surface

- **Status:** PASS
- **YAML:** `packages/aircraft-schema/examples/three_surface_uav.yaml`
- **Backend:** openvsp
- **Components:** fuselage, main_wing, canard, horizontal_tail, vertical_tail, left_engine, right_engine
- **Visual Inspection:** Recommended (complex layout)

| Artifact | Status | Size |
|----------|--------|------|
| aircraft.vsp3 | pass | 289.6 KB |
| aircraft.glb | pass | 84.0 KB |
| aircraft.step | pass | 794.7 KB |
| aircraft.obj | pass | 188.4 KB |
| aircraft_spec.yaml | pass | 2.4 KB |
| generation_log.json | pass | 5.2 KB |
| validation_report.json | pass | 15.2 KB |

**VSPAERO Analysis:** VSPAERO not run for this layout (triggered separately via settings)

- **Frontend 2D preview:** ✅ (verified by `verify-layout-previews.mjs`)

### tandem_wing

- **Status:** PASS
- **YAML:** `packages/aircraft-schema/examples/tandem_wing_uav.yaml`
- **Backend:** openvsp
- **Components:** fuselage, main_wing, rear_wing, center_engine
- **Visual Inspection:** Optional

| Artifact | Status | Size |
|----------|--------|------|
| aircraft.vsp3 | pass | 215.5 KB |
| aircraft.glb | pass | 47.2 KB |
| aircraft.step | pass | 392.0 KB |
| aircraft.obj | pass | 106.1 KB |
| aircraft_spec.yaml | pass | 2.5 KB |
| generation_log.json | pass | 3.7 KB |
| validation_report.json | pass | 15.3 KB |

**VSPAERO Analysis:** VSPAERO not run for this layout (triggered separately via settings)

- **Frontend 2D preview:** ✅ (verified by `verify-layout-previews.mjs`)

### biplane

- **Status:** PASS
- **YAML:** `packages/aircraft-schema/examples/biplane_uav.yaml`
- **Backend:** openvsp
- **Components:** fuselage, main_wing, lower_wing, horizontal_tail, vertical_tail, center_engine
- **Visual Inspection:** Recommended (complex layout)

| Artifact | Status | Size |
|----------|--------|------|
| aircraft.vsp3 | pass | 281.6 KB |
| aircraft.glb | pass | 79.2 KB |
| aircraft.step | pass | 759.8 KB |
| aircraft.obj | pass | 176.7 KB |
| aircraft_spec.yaml | pass | 2.6 KB |
| generation_log.json | pass | 4.6 KB |
| validation_report.json | pass | 15.5 KB |

**VSPAERO Analysis:** VSPAERO not run for this layout (triggered separately via settings)

- **Frontend 2D preview:** ✅ (verified by `verify-layout-previews.mjs`)

### joined_wing

- **Status:** PASS
- **YAML:** `packages/aircraft-schema/examples/joined_wing_uav.yaml`
- **Backend:** openvsp
- **Components:** fuselage, main_wing, rear_wing, center_engine
- **Visual Inspection:** Recommended (complex layout)

| Artifact | Status | Size |
|----------|--------|------|
| aircraft.vsp3 | pass | 215.5 KB |
| aircraft.glb | pass | 47.2 KB |
| aircraft.step | pass | 391.5 KB |
| aircraft.obj | pass | 106.1 KB |
| aircraft_spec.yaml | pass | 2.5 KB |
| generation_log.json | pass | 3.9 KB |
| validation_report.json | pass | 15.3 KB |

**VSPAERO Analysis:** VSPAERO not run for this layout (triggered separately via settings)

- **Frontend 2D preview:** ✅ (verified by `verify-layout-previews.mjs`)

### box_wing

- **Status:** PASS
- **YAML:** `packages/aircraft-schema/examples/box_wing_uav.yaml`
- **Backend:** openvsp
- **Components:** fuselage, main_wing, box_lower_wing, left_endplate, right_endplate, horizontal_tail, vertical_tail, center_engine
- **Visual Inspection:** Recommended (complex layout)

| Artifact | Status | Size |
|----------|--------|------|
| aircraft.vsp3 | pass | 347.8 KB |
| aircraft.glb | pass | 112.0 KB |
| aircraft.step | pass | 1126.4 KB |
| aircraft.obj | pass | 243.1 KB |
| aircraft_spec.yaml | pass | 2.2 KB |
| generation_log.json | pass | 5.2 KB |
| validation_report.json | pass | 14.9 KB |

**VSPAERO Analysis:** VSPAERO not run for this layout (triggered separately via settings)

- **Frontend 2D preview:** ✅ (verified by `verify-layout-previews.mjs`)

### multi_fuselage

- **Status:** PASS
- **YAML:** `packages/aircraft-schema/examples/multi_fuselage_uav.yaml`
- **Backend:** openvsp
- **Components:** left_fuselage, right_fuselage, main_wing, horizontal_tail, vertical_tail, left_engine, right_engine
- **Visual Inspection:** Recommended (complex layout)

| Artifact | Status | Size |
|----------|--------|------|
| aircraft.vsp3 | pass | 346.6 KB |
| aircraft.glb | pass | 79.2 KB |
| aircraft.step | pass | 629.8 KB |
| aircraft.obj | pass | 176.8 KB |
| aircraft_spec.yaml | pass | 2.2 KB |
| generation_log.json | pass | 5.7 KB |
| validation_report.json | pass | 14.8 KB |

**VSPAERO Analysis:** VSPAERO not run for this layout (triggered separately via settings)

- **Frontend 2D preview:** ✅ (verified by `verify-layout-previews.mjs`)

## Summary

| Status | Count | Layouts |
|--------|:-----:|---------|
| ✅ PASS | 11 | conventional, twin_boom, flying_wing, blended_wing_body, canard, three_surface, tandem_wing, biplane, joined_wing, box_wing, multi_fuselage |

## Maturity Assessment

All 11 layouts generate valid artifacts via openvsp backend. All are suitable for **Stable** maturity.

## Recommendations

- Real OpenVSP artifacts generated. Visual inspection of 3D models recommended for geometric plausibility.
- Layouts with multi-surface VSPAERO analysis: canard, three_surface, tandem_wing, joined_wing, biplane, box_wing.
- Per-surface aerodynamic reports not yet available (VSPAERO outputs combined metrics).

## Re-run

```bash
python scripts/validate_layout_matrix.py --backend openvsp
```