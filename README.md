# AeroSpec Agent

Natural-language aircraft concept design workbench prototype.

## Backend

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
set -a
. ./.env
set +a
uvicorn services.api.app.main:app --reload --host "$API_HOST" --port "$API_PORT"
```

For local development without OpenVSP, keep the default fake CAD backend explicit:

```bash
CAD_BACKEND=fake uvicorn services.api.app.main:app --reload --host "$API_HOST" --port "$API_PORT"
```

## Frontend

```bash
cd apps/web
set -a
. ../../.env
set +a
npm install
npm run dev
```

## Tests

```bash
CAD_BACKEND=fake pytest -q
```

## Local MVP verification

Run the backend test suite with the project virtual environment:

```bash
.venv/bin/python -m pytest -q
```

Start the API for local checks, then stop it after verification:

```bash
set -a
. ./.env
set +a
CAD_BACKEND=fake .venv/bin/python -m uvicorn services.api.app.main:app --host "$API_HOST" --port "$API_PORT"
curl -sS "http://$API_HOST:$API_PORT/health"
```

Generate the demo design from the example aircraft spec:

```bash
curl -sS -X POST \
  --data-binary @packages/aircraft-schema/examples/twin_engine_uav.yaml \
  -H "Content-Type: application/x-yaml" \
  "http://$API_HOST:$API_PORT/api/designs/demo/generate"
```

Expected generation result: `status` is `ready`, `progress` is `100`, and files are written under `storage/designs/demo/versions/{version_no}`. With clean demo storage, the first run writes `storage/designs/demo/versions/1`; repeated runs increment to `versions/2`, `versions/3`, and so on. To reset the demo counter before local verification, remove only the demo storage directory:

```bash
rm -rf storage/designs/demo
```

Install and build the frontend:

```bash
cd apps/web
set -a
. ../../.env
set +a
npm install
npm run build
npm run dev
```

The frontend dev server listens on `http://localhost:3900` by default and calls the API at `http://localhost:8900`.

## CAD Backend

The default CAD backend is `fake`, so local development and the standard test suite do not require OpenVSP. The fake backend is deterministic and writes placeholder `vsp3`, `step`, and `glb` artifacts.

Use the default backend explicitly for routine test runs:

```bash
CAD_BACKEND=fake .venv/bin/python -m pytest -q
```

To opt in to real OpenVSP generation, install the OpenVSP Python API that matches the project Python version, then start the API with:

```bash
CAD_BACKEND=openvsp .venv/bin/python -m uvicorn services.api.app.main:app --host "$API_HOST" --port "$API_PORT"
```

This workspace is configured for the official OpenVSP 3.50.2 Ubuntu 24.04 package extracted under the current user:

```bash
OPENVSP_ROOT=/home/z/.local/opt/OpenVSP-3.50.2
OPENVSP_LIB_DIR=/home/z/.local/opt/openvsp-libs/root/usr/lib/x86_64-linux-gnu
LD_LIBRARY_PATH=/home/z/.local/opt/openvsp-libs/root/usr/lib/x86_64-linux-gnu
```

The OpenVSP Python package is installed into `.venv` from `$OPENVSP_ROOT/python/openvsp`. The user-level library directory contains Ubuntu packages `libcminpack1` and `libglew2.2`, unpacked without sudo.

Run the OpenVSP integration test only when that API is installed:

```bash
CAD_BACKEND=openvsp RUN_OPENVSP_TESTS=1 .venv/bin/python -m pytest tests/api/test_openvsp_integration.py -q
```

At this stage the real OpenVSP backend generates `.vsp3`, `.step`, and `.obj` files through the OpenVSP Python API. GLB conversion is not produced by `CAD_BACKEND=openvsp` yet. The web CAD viewer prefers generated `aircraft.glb`, falls back to `aircraft.obj` when available, and keeps the parameter-driven preview visible if a generated model file cannot be loaded.

## Chat Endpoint

The chat endpoint connects to an OpenAI-compatible LLM to parse natural language into aircraft specs. Multi-turn conversation with spec modification is supported.

Set the following environment variables in `.env`:

```
OPENAI_API_KEY=sk-your-key
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
```

Then use the web UI chat panel or curl:

```bash
curl -sS -N -X POST "http://localhost:8900/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"demo-chat","message":"设计一架翼展12米双发无人机"}'
```

The endpoint returns an SSE stream with events: `message` (token-by-token text), `tool_call` (function invocation), `generation_started`, `generation_complete` (with version_no and files), and `error`.
