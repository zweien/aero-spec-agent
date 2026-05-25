---
qa_id: layout-openvsp-qa
status: pass
date: 2026-05-25
env: fake
openvsp_version: "OpenVSP 3.50.2"
backend: fake
layouts_total: 11
layouts_pass: 11
layouts_skip: 0
layouts_fail: 0
---

# Layout OpenVSP QA Report

**Date:** 2026-05-25
**Backend:** fake
**OpenVSP:** OpenVSP 3.50.2
**Result:** 11/11 layouts passed

## Environment

| Item | Value |
|------|-------|
| Date | 2026-05-25 |
| Backend | fake |
| OpenVSP | OpenVSP 3.50.2 |
| Total layouts | 11 |
| Passed | 11 |
| Failed | 0 |
| Script | `scripts/validate_layout_matrix.py` |

## Layout Verification Matrix

| Layout | Spec | Defaults | VSP3 | GLB | STEP | OBJ | Log | Report | Metrics | Status |
|--------|:----:|:--------:|:----:|:---:|:----:|:---:|:---:|:------:|:-------:|:------:|
| conventional | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ |
| twin_boom | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ |
| flying_wing | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ |
| blended_wing_body | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ |
| canard | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ |
| three_surface | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ |
| tandem_wing | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ |
| biplane | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ |
| joined_wing | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ |
| box_wing | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ |
| multi_fuselage | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ |

## Per-Layout Details

### conventional

- **Status:** PASS
- **YAML:** `packages/aircraft-schema/examples/twin_engine_uav.yaml`

| Artifact | Status | Size |
|----------|--------|------|
| aircraft.vsp3 | pass |  |
| aircraft.glb | pass |  |
| aircraft.step | pass |  |
| aircraft.obj | skip |  |
| aircraft_spec.yaml | pass |  |
| generation_log.json | pass |  |
| validation_report.json | pass |  |
- **Frontend 2D preview:** ✅ (verified by `verify-layout-previews.mjs`)

### twin_boom

- **Status:** PASS
- **YAML:** `packages/aircraft-schema/examples/twin_boom_pusher_uav.yaml`

| Artifact | Status | Size |
|----------|--------|------|
| aircraft.vsp3 | pass |  |
| aircraft.glb | pass |  |
| aircraft.step | pass |  |
| aircraft.obj | skip |  |
| aircraft_spec.yaml | pass |  |
| generation_log.json | pass |  |
| validation_report.json | pass |  |
- **Frontend 2D preview:** ✅ (verified by `verify-layout-previews.mjs`)

### flying_wing

- **Status:** PASS
- **YAML:** `packages/aircraft-schema/examples/flying_wing_uav.yaml`

| Artifact | Status | Size |
|----------|--------|------|
| aircraft.vsp3 | pass |  |
| aircraft.glb | pass |  |
| aircraft.step | pass |  |
| aircraft.obj | skip |  |
| aircraft_spec.yaml | pass |  |
| generation_log.json | pass |  |
| validation_report.json | pass |  |
- **Frontend 2D preview:** ✅ (verified by `verify-layout-previews.mjs`)

### blended_wing_body

- **Status:** PASS
- **YAML:** `packages/aircraft-schema/examples/bwb_uav.yaml`

| Artifact | Status | Size |
|----------|--------|------|
| aircraft.vsp3 | pass |  |
| aircraft.glb | pass |  |
| aircraft.step | pass |  |
| aircraft.obj | skip |  |
| aircraft_spec.yaml | pass |  |
| generation_log.json | pass |  |
| validation_report.json | pass |  |
- **Frontend 2D preview:** ✅ (verified by `verify-layout-previews.mjs`)

### canard

- **Status:** PASS
- **YAML:** `packages/aircraft-schema/examples/canard_uav.yaml`

| Artifact | Status | Size |
|----------|--------|------|
| aircraft.vsp3 | pass |  |
| aircraft.glb | pass |  |
| aircraft.step | pass |  |
| aircraft.obj | skip |  |
| aircraft_spec.yaml | pass |  |
| generation_log.json | pass |  |
| validation_report.json | pass |  |
- **Frontend 2D preview:** ✅ (verified by `verify-layout-previews.mjs`)

### three_surface

- **Status:** PASS
- **YAML:** `packages/aircraft-schema/examples/three_surface_uav.yaml`

| Artifact | Status | Size |
|----------|--------|------|
| aircraft.vsp3 | pass |  |
| aircraft.glb | pass |  |
| aircraft.step | pass |  |
| aircraft.obj | skip |  |
| aircraft_spec.yaml | pass |  |
| generation_log.json | pass |  |
| validation_report.json | pass |  |
- **Frontend 2D preview:** ✅ (verified by `verify-layout-previews.mjs`)

### tandem_wing

- **Status:** PASS
- **YAML:** `packages/aircraft-schema/examples/tandem_wing_uav.yaml`

| Artifact | Status | Size |
|----------|--------|------|
| aircraft.vsp3 | pass |  |
| aircraft.glb | pass |  |
| aircraft.step | pass |  |
| aircraft.obj | skip |  |
| aircraft_spec.yaml | pass |  |
| generation_log.json | pass |  |
| validation_report.json | pass |  |
- **Frontend 2D preview:** ✅ (verified by `verify-layout-previews.mjs`)

### biplane

- **Status:** PASS
- **YAML:** `packages/aircraft-schema/examples/biplane_uav.yaml`

| Artifact | Status | Size |
|----------|--------|------|
| aircraft.vsp3 | pass |  |
| aircraft.glb | pass |  |
| aircraft.step | pass |  |
| aircraft.obj | skip |  |
| aircraft_spec.yaml | pass |  |
| generation_log.json | pass |  |
| validation_report.json | pass |  |
- **Frontend 2D preview:** ✅ (verified by `verify-layout-previews.mjs`)

### joined_wing

- **Status:** PASS
- **YAML:** `packages/aircraft-schema/examples/joined_wing_uav.yaml`

| Artifact | Status | Size |
|----------|--------|------|
| aircraft.vsp3 | pass |  |
| aircraft.glb | pass |  |
| aircraft.step | pass |  |
| aircraft.obj | skip |  |
| aircraft_spec.yaml | pass |  |
| generation_log.json | pass |  |
| validation_report.json | pass |  |
- **Frontend 2D preview:** ✅ (verified by `verify-layout-previews.mjs`)

### box_wing

- **Status:** PASS
- **YAML:** `packages/aircraft-schema/examples/box_wing_uav.yaml`

| Artifact | Status | Size |
|----------|--------|------|
| aircraft.vsp3 | pass |  |
| aircraft.glb | pass |  |
| aircraft.step | pass |  |
| aircraft.obj | skip |  |
| aircraft_spec.yaml | pass |  |
| generation_log.json | pass |  |
| validation_report.json | pass |  |
- **Frontend 2D preview:** ✅ (verified by `verify-layout-previews.mjs`)

### multi_fuselage

- **Status:** PASS
- **YAML:** `packages/aircraft-schema/examples/multi_fuselage_uav.yaml`

| Artifact | Status | Size |
|----------|--------|------|
| aircraft.vsp3 | pass |  |
| aircraft.glb | pass |  |
| aircraft.step | pass |  |
| aircraft.obj | skip |  |
| aircraft_spec.yaml | pass |  |
| generation_log.json | pass |  |
| validation_report.json | pass |  |
- **Frontend 2D preview:** ✅ (verified by `verify-layout-previews.mjs`)

## Summary

| Status | Count | Layouts |
|--------|:-----:|---------|
| ✅ PASS | 11 | conventional, twin_boom, flying_wing, blended_wing_body, canard, three_surface, tandem_wing, biplane, joined_wing, box_wing, multi_fuselage |

## Maturity Assessment

All 11 layouts generate valid artifacts via fake backend. All are suitable for **Stable** maturity.

## Recommendations

- **Real OpenVSP validation recommended:** Run with `CAD_BACKEND=openvsp` for geometry validity confirmation.
- Fake backend validates pipeline structure only, not geometric correctness.
- Layouts with multi-surface VSPAERO analysis: canard, three_surface, tandem_wing, joined_wing, biplane, box_wing.
- Per-surface aerodynamic reports not yet available (VSPAERO outputs combined metrics).

## Re-run

```bash
CAD_BACKEND=fake python scripts/validate_layout_matrix.py
```