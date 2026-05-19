# OpenVSP Deep Design Validation Report

**Date:** 2026-05-19
**Validator:** automated check
**Status:** PASS

---

## Environment

| Item | Value |
|------|-------|
| OS | Linux 6.17.0-23-generic |
| Python | 3.12 |
| OpenVSP package | Installed (`openvsp` in .venv) |
| OpenVSP version | 3.50.2 (package metadata) |
| System dependency | `libcminpack1` — installed |

## OpenVSP Integration Test

```bash
CAD_BACKEND=openvsp RUN_OPENVSP_TESTS=1 .venv/bin/python -m pytest tests/api/test_openvsp_integration.py -q
# 1 passed in 0.97s
```

## Validation Results

### Case 1: Single-engine long-endurance UAV

- **Design ID:** `openvsp-test-1`
- **Spec:** 翼展10m、单发、上单翼、常规尾翼
- **Generation time:** 353ms
- **Status:** succeeded

| Artifact | Size | Present |
|----------|------|---------|
| aircraft.vsp3 | 254 KB | Yes |
| aircraft.step | 608 KB | Yes |
| aircraft.obj | 142 KB | Yes |
| aircraft.glb | 65 KB | Yes |
| aircraft_spec.yaml | 1.3 KB | Yes |
| generation_log.json | 4.3 KB | Yes |
| validation_report.json | 13.5 KB | Yes |

**OpenVSP components generated:** fuselage, main_wing, horizontal_tail, vertical_tail, center_engine

### Case 2: Twin-engine logistics UAV

- **Design ID:** `openvsp-test-2`
- **Spec:** 翼展8m、双发、下单翼、常规尾翼
- **Generation time:** 183ms
- **Status:** succeeded

| Artifact | Size | Present |
|----------|------|---------|
| aircraft.vsp3 | 262 KB | Yes |
| aircraft.step | 622 KB | Yes |
| aircraft.obj | 154 KB | Yes |
| aircraft.glb | 70 KB | Yes |
| aircraft_spec.yaml | 1.3 KB | Yes |
| generation_log.json | 5.2 KB | Yes |
| validation_report.json | 13.4 KB | Yes |

**OpenVSP components generated:** fuselage, main_wing, horizontal_tail, vertical_tail, left_engine, right_engine

## Metrics Summary

| Metric | Case 1 | Case 2 | Expected | Pass |
|--------|--------|--------|----------|------|
| Generation time | 353ms | 183ms | < 120s | Yes |
| Artifact files | 7 | 7 | 5+ | Yes |
| Generation failure | 0 | 0 | < 10% | Yes |
| Deadlock count | 0 | 0 | 0 | Yes |

## Conclusion

**OpenVSP backend is fully operational.** Both single-engine and twin-engine configurations generate valid CAD artifacts in under 400ms. All 7 expected artifact files are produced per generation.

**Can enter real OpenVSP testing:** YES
