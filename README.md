# AeroSpec Agent

Natural-language aircraft concept design workbench prototype.

## Backend

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
uvicorn services.api.app.main:app --reload --port 8000
```

## Tests

```bash
pytest -q
```

## Local MVP verification

Run the backend test suite with the project virtual environment:

```bash
.venv/bin/python -m pytest -q
```

Start the API for local checks, then stop it after verification:

```bash
.venv/bin/python -m uvicorn services.api.app.main:app --host 127.0.0.1 --port 8000
curl -sS http://127.0.0.1:8000/health
```

Generate the demo design from the example aircraft spec:

```bash
curl -sS -X POST \
  --data-binary @packages/aircraft-schema/examples/twin_engine_uav.yaml \
  -H "Content-Type: application/x-yaml" \
  http://127.0.0.1:8000/api/designs/demo/generate
```

Expected generation result: `status` is `ready`, `progress` is `100`, and files are written under `storage/designs/demo/versions/{version_no}`. With clean demo storage, the first run writes `storage/designs/demo/versions/1`; repeated runs increment to `versions/2`, `versions/3`, and so on. To reset the demo counter before local verification, remove only the demo storage directory:

```bash
rm -rf storage/designs/demo
```

Install and build the frontend:

```bash
cd apps/web
npm install
npm run build
```

## CAD Backend

The MVP uses a deterministic fake CAD backend for local tests. A real OpenVSP backend is isolated behind `services/workers/cad_worker/openvsp_generator/backend.py` and imports `openvsp` lazily.
