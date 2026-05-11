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

## CAD Backend

The MVP uses a deterministic fake CAD backend for local tests. A real OpenVSP backend is isolated behind `services/workers/cad_worker/openvsp_generator/backend.py` and imports `openvsp` lazily.
