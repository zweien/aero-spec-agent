<div align="center">

# AeroSpec Agent

**Natural-language aircraft concept design workbench**

Describe an aircraft in plain language — get parametric CAD models, aerodynamic analysis, and an interactive 3D preview.

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14-000?logo=next.js&logoColor=white)](https://nextjs.org/)
[![OpenVSP](https://img.shields.io/badge/OpenVSP-3.50-1E88E5?logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHRleHQgZmlsbD0id2hpdGUiIGZvbnQtc2l6ZT0iMTIiIHk9IjE2IiB4PSIyIj5WU1A8L3RleHQ+PC9zdmc+)](http://openvsp.org/)

[Report Bug](https://github.com/zweien/aero-spec-agent/issues) · [Request Feature](https://github.com/zweien/aero-spec-agent/issues) · [View Demo](#quick-start)

</div>

---

## Screenshot

![AeroSpec Agent](docs/screenshots/openvsp-single-engine.png)

---

## Features

- **Conversational Design** — Describe your aircraft in natural language; the LLM parses requirements into a structured spec, calls OpenVSP to generate CAD, and streams results back.
- **Interactive 3D Preview** — Three.js viewer with GLB/OBJ model loading and a parameter-driven wireframe fallback. Orbit, zoom, and inspect the design in real time.
- **Parametric CAD Generation** — OpenVSP builds fuselage, wing, tail, and engine nacelles from the spec. Exports `.vsp3`, `.step`, `.obj`, `.glb` artifacts per version.
- **Aerodynamic Analysis** — Optional VSPAERO panel-method sweep (CL/CD/CM vs alpha, optimal L/D, CL_alpha, CD0 estimate) with results shown in the bottom panel.
- **Version History** — Every generation produces an auto-incrementing version directory with all artifacts and a validation report.
- **Live Parameter Editing** — Drag sliders to tweak dimensions; batch multiple changes and submit them through the chat channel for a full re-analysis.
- **Runtime Settings** — Switch between Fake/OpenVSP backends and toggle VSPAERO analysis from the UI — no restart needed.

## Architecture

```
┌─────────────────────────────────────────────┐
│  Next.js Frontend (apps/web)                 │
│  ChatPanel · CadViewer · ParameterPanel      │
│  SettingsPanel · VersionPanel                │
└──────────────────┬──────────────────────────┘
                   │ HTTP / SSE
┌──────────────────▼──────────────────────────┐
│  FastAPI Backend (services/api)              │
│  LLM Chat · JobRunner · VersionStore         │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  CAD Worker (services/workers)               │
│  FakeCadBackend ── deterministic placeholders│
│  OpenVspBackend ── OpenVSP → STEP/OBJ/GLB   │
│  VSPAERO Analysis ── panel method sweep      │
└─────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- An OpenAI-compatible LLM API key (DeepSeek, OpenAI, etc.)

### 1. Clone & Install

```bash
git clone https://github.com/zweien/aero-spec-agent.git
cd aero-spec-agent

# Backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

# Frontend
cd apps/web && npm install && cd ../..
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — set OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
```

### 3. Run

```bash
# Terminal 1 — Backend (fake CAD backend, no OpenVSP needed)
set -a && . ./.env && set +a
CAD_BACKEND=fake .venv/bin/python -m uvicorn services.api.app.main:app --host "$API_HOST" --port "$API_PORT"

# Terminal 2 — Frontend
cd apps/web
set -a && . ../../.env && set +a
npm run dev
```

Open http://localhost:3900 and start describing your aircraft.

### With Real OpenVSP

If you have [OpenVSP 3.50.2](http://openvsp.org/) with Python bindings installed:

```bash
CAD_BACKEND=openvsp .venv/bin/python -m uvicorn services.api.app.main:app --host "$API_HOST" --port "$API_PORT"
```

You can also switch backends at runtime from the Settings panel in the UI.

## Usage

### Chat-driven Design

Type natural language in the chat panel:

> "设计一架翼展12米、双发、上单翼、常规尾翼的固定翼无人机"

The LLM generates a full `AircraftSpec`, calls OpenVSP, and shows the 3D model with a tool card in the conversation.

### Parameter Editing

Drag sliders to adjust wing span, chord, sweep, etc. Changes are batched locally — click **"确认修改"** to submit all changes through the chat, which triggers a full re-generation with analysis.

### Version History

Each generation creates a versioned directory:

```
storage/designs/{design_id}/versions/{N}/
├── aircraft_spec.yaml
├── aircraft.vsp3
├── aircraft.step
├── aircraft.obj
├── aircraft.glb
├── generation_log.json
└── validation_report.json
```

## Screenshots

<table>
  <tr>
    <td><img src="docs/screenshots/multi-turn-modification.png" alt="Multi-turn modification" /></td>
    <td><img src="docs/screenshots/markdown-rendering.png" alt="Markdown rendering" /></td>
  </tr>
  <tr>
    <td align="center">Multi-turn modification</td>
    <td align="center">Design analysis in chat</td>
  </tr>
</table>

## Testing

```bash
# Run all tests (fake backend, no OpenVSP needed)
CAD_BACKEND=fake .venv/bin/python -m pytest -q

# OpenVSP integration tests (requires OpenVSP installed)
CAD_BACKEND=openvsp RUN_OPENVSP_TESTS=1 .venv/bin/python -m pytest tests/api/test_openvsp_integration.py -q

# Lint
.venv/bin/python -m ruff check .
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 · React · Three.js · TypeScript |
| Backend | FastAPI · Pydantic · SSE |
| CAD Engine | OpenVSP 3.50.2 (Python API) |
| Aero Analysis | VSPAERO Panel Method |
| LLM | OpenAI-compatible API (DeepSeek / OpenAI) |
| 3D Viewer | Three.js GLB/OBJ Loader |

## Project Structure

```
aero-spec-agent/
├── apps/web/                  # Next.js frontend
├── services/
│   ├── api/                   # FastAPI backend
│   └── workers/cad_worker/    # OpenVSP CAD generation
├── packages/aircraft-schema/  # Spec definitions & examples
├── tests/api/                 # Backend test suite
├── storage/                   # Generated design artifacts
└── pyproject.toml             # Python project config
```

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [OpenVSP](http://openvsp.org/) — Open Vehicle Sketch Pad by NASA
- [VSPAERO](http://openvsp.org/) — Panel-method aerodynamic analysis
- [Three.js](https://threejs.org/) — 3D graphics for the web

---

<div align="center">

**[⬆ Back to Top](#aerospec-agent)**

</div>
