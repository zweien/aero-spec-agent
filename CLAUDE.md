# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AeroSpec Agent is a natural-language aircraft concept design workbench prototype. Users describe an aircraft in structured YAML, the backend generates CAD models via OpenVSP, and the Next.js frontend displays a 3D preview alongside design parameters and version history.

## Commands

### Backend (Python, FastAPI)

```bash
# Install (first time)
python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"

# Run API (fake CAD backend, no OpenVSP needed)
set -a && . ./.env && set +a
CAD_BACKEND=fake .venv/bin/python -m uvicorn services.api.app.main:app --host "$API_HOST" --port "$API_PORT"

# Run API (real OpenVSP)
CAD_BACKEND=openvsp .venv/bin/python -m uvicorn services.api.app.main:app --host "$API_HOST" --port "$API_PORT"

# Tests (standard suite, uses fake backend)
CAD_BACKEND=fake .venv/bin/python -m pytest -q

# Single test file
CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_generation_api.py -q

# OpenVSP integration tests (requires OpenVSP installed)
CAD_BACKEND=openvsp RUN_OPENVSP_TESTS=1 .venv/bin/python -m pytest tests/api/test_openvsp_integration.py -q

# Lint
.venv/bin/python -m ruff check .
```

### Frontend (Next.js + TypeScript + Three.js)

```bash
cd apps/web
set -a && . ../../.env && set +a
npm install
npm run dev     # dev server on http://localhost:3900
npm run build   # production build
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  apps/web (Next.js)                                  │
│  page.tsx → ChatPanel / ParameterPanel / CadViewer   │
│            / VersionPanel                             │
│  CadViewer → AircraftThreePreview (three.js scene)   │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP /api/*
┌──────────────────────▼──────────────────────────────┐
│  services/api (FastAPI)                               │
│  main.py → designs router                            │
│  routers/designs.py → JobRunner → VersionStore       │
│    POST /api/designs/{id}/generate (YAML body)       │
│    GET  /api/jobs/{job_id}                           │
│    GET  /api/designs/{id}/versions/{no}              │
│    GET  /api/designs/{id}/versions/{no}/files/{name} │
│    GET  /health                                      │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  services/workers/cad_worker/openvsp_generator        │
│  backend_factory → CadBackend protocol                │
│    FakeCadBackend: deterministic placeholders         │
│    OpenVspBackend: OpenVSP → vsp3/step/obj → glb     │
│  generate_aircraft.py orchestrates generation,        │
│    writes generation_log.json + validation_report.json│
│  Geometry builders: create_fuselage, create_wing,    │
│    create_tail, create_engine → via OpenVspAdapter   │
└─────────────────────────────────────────────────────┘
```

### Key data flow

1. Client POSTs YAML spec to `/api/designs/{id}/generate`
2. `JobRunner.generate()` creates a versioned output dir under `storage/designs/{id}/versions/{N}/`
3. `generate_aircraft()` calls the selected `CadBackend` (fake or openvsp)
4. Output artifacts per version: `aircraft_spec.yaml`, `aircraft.vsp3`, `aircraft.step`, `aircraft.glb`, `generation_log.json`, `validation_report.json`
5. Frontend polls `/api/jobs/{id}` for status, then fetches generated files

### Spec schema

`AircraftSpec` (Pydantic model, `services/api/app/schemas/aircraft_spec.py`) defines the aircraft configuration. Each scalar field carries `value`, `unit`, `source` (user/inferred/rule_default/system_default), `confidence`, and optional `reason`. Example spec at `packages/aircraft-schema/examples/twin_engine_uav.yaml`.

### CAD backend selection

Controlled by `CAD_BACKEND` env var. `fake` (default) produces deterministic placeholder files. `openvsp` requires the OpenVSP 3.50.2 Python API installed locally. The `FakeCadBackend` is used for all standard tests.

### Storage layout

`storage/designs/{design_id}/versions/{version_no}/` — each generation creates an auto-incrementing version directory with all artifacts. `VersionStore` manages thread-safe version creation.

### Frontend

Single-page app with four panels: ChatPanel, ParameterPanel, CadViewer (Three.js with GLB/OBJ loading and parameter-driven wireframe fallback), VersionPanel. API base URL configured via `NEXT_PUBLIC_API_BASE_URL`.

## Conventions

- Python: ruff for linting, line-length 100, target Python 3.11+
- Tests in `tests/api/`, pytest with `pythonpath = ["."]`
- The fake backend must be used for all tests unless explicitly testing OpenVSP (`RUN_OPENVSP_TESTS=1`)
- Design IDs must match `^[A-Za-z0-9_-]+$`
- Version directories auto-increment; no deletion or reuse
