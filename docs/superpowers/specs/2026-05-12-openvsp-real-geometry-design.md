# OpenVSP Real Geometry MVP Design

## Goal

Build the next development slice for AeroSpec Agent: convert the existing `aircraft_spec.yaml` example into a real OpenVSP `.vsp3` aircraft model and verify the generated geometry at the parameter level.

This phase intentionally stops before STEP, GLB conversion, React Three Fiber, natural-language parsing, or LangGraph. The only goal is to replace the fake CAD path with a real, testable OpenVSP geometry path while keeping the current fake backend for environments without OpenVSP.

## Current State

The project already has:

- FastAPI generation API and version storage.
- Strict `AircraftSpec` Pydantic schema.
- `FakeCadBackend` that writes placeholder `.vsp3`, `.step`, and `.glb` files.
- `OpenVspBackend` shell that imports `openvsp`, creates one fuselage and one wing, and writes a `.vsp3`.
- Frontend workflow that calls the generation API and displays generated files.

The current limitation is that CAD output is not a real aircraft model. The fake backend is useful for tests, but it does not validate OpenVSP installation, parameter mapping, geometry creation, or actual `.vsp3` output.

## OpenVSP Constraints

OpenVSP official documentation states that the API exposes GUI functionality for headless automation and integration. It also warns that the Python version must match the version OpenVSP was compiled with. That makes environment detection a first-class requirement, not an afterthought.

References:

- OpenVSP Python API docs: https://openvsp.org/pyapi_docs/latest/
- OpenVSP File I/O API: https://openvsp.org/api_docs/latest/group___file_i_o.html

Relevant API surface for this phase:

- `ClearVSPModel()`
- `AddGeom(type, parent="")`
- `SetParmVal(...)`
- `Update()`
- `WriteVSPFile(path, SET_ALL)`
- OpenVSP error manager calls if available in the installed Python API

`ExportFile(...)` exists and supports many formats, but export conversion is outside this phase.

## Scope

### In Scope

1. Detect whether real OpenVSP Python API is available.
2. Add a backend selection layer:
   - default: fake backend
   - `CAD_BACKEND=openvsp`: real OpenVSP backend
3. Implement real OpenVSP `.vsp3` generation for the existing twin-engine UAV spec.
4. Create simple aircraft geometry:
   - fuselage
   - main wing
   - horizontal tail
   - vertical tail
   - two engine nacelles
5. Record component IDs and intended parameter values in `generation_log.json`.
6. Produce `validation_report.json` based on values applied to OpenVSP and files written.
7. Keep all existing fake backend tests passing without OpenVSP installed.
8. Add opt-in integration tests that run only when OpenVSP is installed and explicitly enabled.

### Out Of Scope

- STEP export.
- GLB generation or real frontend 3D rendering.
- Natural-language parsing.
- LangGraph orchestration.
- Aerodynamic analysis.
- High-fidelity airfoil, control surface, propulsion, or structural modeling.
- Accurate aircraft design validation beyond parameter-level checks.

## Architecture

### Backend Selection

Add a small factory in the CAD worker boundary:

```text
CAD_BACKEND unset or "fake"      -> FakeCadBackend
CAD_BACKEND "openvsp"            -> OpenVspBackend
invalid value                    -> explicit configuration error
```

The API and `JobRunner` should depend on the `CadBackend` protocol, not direct backend classes. This keeps the current test path simple and lets local users opt into real OpenVSP only when their environment is ready.

### OpenVSP Builder Modules

Split the real backend into focused units:

```text
services/workers/cad_worker/openvsp_generator/
  backend.py
  backend_factory.py
  openvsp_adapter.py
  create_fuselage.py
  create_wing.py
  create_tail.py
  create_engine.py
  verify_model.py
```

Responsibilities:

- `openvsp_adapter.py`: wraps `openvsp` import, common API calls, error collection, and missing-install errors.
- `create_fuselage.py`: creates fuselage geometry from `spec.fuselage`.
- `create_wing.py`: creates main wing from `spec.wing`.
- `create_tail.py`: creates horizontal and vertical tail using simple wing-like surfaces.
- `create_engine.py`: creates symmetric nacelles based on `spec.engine.count`.
- `verify_model.py`: validates written files and recorded component/parameter metadata.
- `backend.py`: orchestrates those modules inside `OpenVspBackend.generate()`.

This keeps OpenVSP-specific API calls isolated from API routing and job storage.

## Geometry Mapping

Use conservative, deterministic mappings from the current schema.

### Fuselage

Input:

- `fuselage.length`
- `fuselage.max_diameter`

Output:

- One `FUSELAGE` geom.
- Length set from spec when an OpenVSP length parameter is available.
- Diameter applied to available fuselage cross-section or equivalent parameter when available.

### Main Wing

Input:

- `wing.span`
- `wing.root_chord`
- `wing.tip_chord`
- `wing.sweep`
- `wing.dihedral`
- `wing.position`

Output:

- One `WING` geom.
- Total span is mapped as full aircraft span.
- Root/tip chord, sweep, and dihedral are applied when matching OpenVSP parameters are available.
- Vertical placement uses:
  - high wing: positive Z offset
  - mid wing: near fuselage centerline
  - low wing: negative Z offset

### Tail

Input:

- `tail.type == conventional`
- derived size from wing and fuselage dimensions

Output:

- Horizontal tail as a smaller `WING`.
- Vertical tail as a smaller `WING` rotated or oriented vertically.
- Tail placement near aft fuselage.

### Engines

Input:

- `engine.count`
- `engine.position`

Output:

- For `engine.count == 2`, create two symmetric nacelles.
- Nacelles are placed under the wing and offset left/right.
- For MVP, nacelles may use `POD` if available, otherwise simplified `FUSELAGE`.
- Unsupported engine counts fail clearly in real backend instead of silently producing wrong geometry.

## Validation

Validation remains lightweight but must stop being pure spec echo.

Required report entries:

```json
{
  "backend": {
    "expected": "openvsp",
    "actual": "OpenVspBackend",
    "status": "pass"
  },
  "vsp3.exists": {
    "expected": true,
    "actual": true,
    "status": "pass"
  },
  "wing.span": {
    "expected": 12.0,
    "actual": 12.0,
    "status": "pass"
  },
  "engine.count": {
    "expected": 2,
    "actual": 2,
    "status": "pass"
  }
}
```

`actual` can initially come from the applied OpenVSP parameter log instead of geometric bounding-box measurement. Bounding-box measurement is deferred until a later mesh/export phase.

The report should also include a clear `failed` status and message when:

- OpenVSP Python API is unavailable.
- A required OpenVSP geometry cannot be created.
- A required parameter cannot be set.
- `.vsp3` is not written or is empty.

## Error Handling

OpenVSP failures should be explicit and actionable:

- Missing `openvsp` import: `OpenVspUnavailableError`
- Unsupported spec feature: `UnsupportedGeometryError`
- OpenVSP API returned no geometry ID: `OpenVspGenerationError`
- File write failure: `OpenVspGenerationError`

The `JobRunner` should keep its current `failed` behavior and store the error message in `JobRecord.error_message`.

## Testing Strategy

### Unit Tests Without OpenVSP

These must run in normal CI/local environments:

- Backend factory selects fake backend by default.
- Backend factory selects OpenVSP backend only when `CAD_BACKEND=openvsp`.
- Invalid backend value raises a configuration error.
- OpenVSP adapter raises a clear unavailable error when `openvsp` cannot be imported.
- Geometry mapping functions can be tested using a fake OpenVSP module object that records calls.
- Existing API and job tests continue to use fake backend.

### Opt-In Integration Tests With OpenVSP

Integration tests must be skipped unless both are true:

```text
RUN_OPENVSP_TESTS=1
CAD_BACKEND=openvsp
```

Integration acceptance:

- Load `packages/aircraft-schema/examples/twin_engine_uav.yaml`.
- Generate into a temp directory with `OpenVspBackend`.
- Assert `aircraft.vsp3` exists and is non-empty.
- Assert validation report says backend, vsp3, wing span, and engine count pass.

## API And Frontend Impact

No new API endpoint is required.

The existing generation endpoint should work with backend selection through environment:

```bash
CAD_BACKEND=openvsp .venv/bin/python -m uvicorn services.api.app.main:app --host "$API_HOST" --port "$API_PORT"
```

The frontend should continue to display file paths and status. It does not need a real 3D viewer in this phase.

## Documentation

README should add an OpenVSP section:

- How to keep using fake backend.
- How to opt into real OpenVSP.
- Environment variables:
  - `CAD_BACKEND=fake`
  - `CAD_BACKEND=openvsp`
  - `RUN_OPENVSP_TESTS=1`
- Known limitation: Python version must match the OpenVSP distribution.

## Acceptance Criteria

1. `CAD_BACKEND=fake .venv/bin/python -m pytest -q` passes without OpenVSP installed.
2. `CAD_BACKEND=openvsp` fails clearly if `openvsp` cannot be imported.
3. With OpenVSP installed and `RUN_OPENVSP_TESTS=1`, integration test writes a non-empty `aircraft.vsp3`.
4. The generation API still returns `ready` with fake backend.
5. The generation API can return `ready` with OpenVSP backend in a configured environment.
6. No STEP or GLB real export is required for this phase.

## Follow-Up After This Phase

Once real `.vsp3` generation is stable, the next independent phases are:

1. Export mesh or STL from OpenVSP.
2. Convert exported geometry to GLB.
3. Replace the frontend GLB path display with a real 3D viewer.
4. Add natural-language to spec generation.
5. Add spec patch and regeneration flows.
