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

Run the OpenVSP integration test only when that API is installed:

```bash
CAD_BACKEND=openvsp RUN_OPENVSP_TESTS=1 .venv/bin/python -m pytest tests/api/test_openvsp_integration.py -q
```

At this stage the real OpenVSP backend generates a `.vsp3` file only. STEP and GLB export remain fake-backend placeholders and are not produced by `CAD_BACKEND=openvsp`.
