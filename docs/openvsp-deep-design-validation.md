# OpenVSP Deep Design Validation Report

**Date:** 2026-05-19
**Validator:** automated check
**Status:** BLOCKED — missing system library

---

## Environment

| Item | Value |
|------|-------|
| OS | Linux 6.17.0-23-generic |
| Python | 3.12 |
| OpenVSP package | Installed (`openvsp` in .venv) |
| OpenVSP version | 3.50.2 (package metadata) |
| System dependency | **MISSING:** `libcminpack.so.1` |

## Diagnosis

```
$ python -c "import openvsp"
ImportError: libcminpack.so.1: cannot open shared object file: No such file or directory
```

The OpenVSP Python package is installed in the virtual environment, but the runtime shared library `libcminpack.so.1` is not present on the system. This library is a dependency of OpenVSP's numerical solver.

## Required Fix

Install the missing system library:

```bash
# Ubuntu/Debian
sudo apt-get install libcminpack1

# Or build from source: https://github.com/debrouxl/cminpack
```

After installing, verify:

```bash
.venv/bin/python -c "import openvsp; print('OpenVSP ready')"
```

## Planned Test Cases

Once the system library is available, run these two cases:

### Case 1: Single-engine long-endurance UAV

- **Chat input:** "设计一架翼展10米、单发、上单翼的长航时无人机"
- **Deep Design:** Quick explore (2 variants), no strategy
- **Verify:**
  - `/api/deep-design/stream` returns SSE events
  - `generation_progress` events push correctly
  - CAD artifacts generated: `aircraft.vsp3`, `aircraft.glb`, `aircraft.step`, `generation_log.json`, `validation_report.json`
  - CAD Viewer loads model
  - "查看模型" works
  - "设为当前方案" works
  - No deadlock, no queued stall

### Case 2: Logistics UAV with endurance optimization

- **Chat input:** "设计一架翼展8米、双发、下单翼的物流无人机"
- **Deep Design:** Standard explore (3 variants), "长航时优化" strategy
- **Verify:** Same checklist as Case 1, plus:
  - 3 variants all complete
  - Report contains comparison table
  - Each variant has different aerodynamic metrics

## Expected Results

| Metric | Expected |
|--------|----------|
| Case 1 total time | < 120s (2 variants) |
| Case 2 total time | < 180s (3 variants) |
| Artifact files per variant | 5+ (spec, vsp3, step, glb, obj, log, report) |
| Generation failure rate | < 10% |
| Deadlock count | 0 |

## Current Status

**Cannot proceed with OpenVSP validation until `libcminpack.so.1` is installed.**

### Workaround

User beta testing can proceed with `CAD_BACKEND=fake`. The fake backend:
- Produces deterministic placeholder artifacts
- Exercises all the same code paths as OpenVSP (same JobRunner, VersionStore, SSE streaming)
- Does not validate actual 3D geometry correctness

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| OpenVSP geometry differs from fake | High | Medium | Separate OpenVSP-specific test pass before wider release |
| OpenVSP crashes on certain specs | Medium | High | Error policy `warn` mode catches failures gracefully |
| Performance difference | High | Low | Fake is faster; real times will be longer |

## Recommendation

1. Install `libcminpack1` system package
2. Run `CAD_BACKEND=openvsp .venv/bin/python -m pytest tests/api/test_openvsp_integration.py -q` to verify basic OpenVSP
3. Then run Case 1 and Case 2 above
4. Record actual timings and artifact verification
5. Update this document with results
