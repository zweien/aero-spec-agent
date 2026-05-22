#!/usr/bin/env python3
"""Seed demo design data for v0.1.0 showcase.

Generates 3 aircraft designs using the configured CAD backend (default: fake).
Demo design_ids use 'demo-' prefix to isolate from production data.

Usage: python scripts/seed_demo_designs.py [--json]
"""

import copy
import json
import os
import sys
import time
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _base_spec() -> dict:
    """Load the twin_engine_uav example as a base spec."""
    with open(PROJECT_ROOT / "packages/aircraft-schema/examples/twin_engine_uav.yaml") as f:
        return yaml.safe_load(f)


def _set(spec: dict, path: str, value) -> None:
    """Set a nested value in spec dict using dot-separated path."""
    keys = path.split(".")
    node = spec
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    last_key = keys[-1]
    existing = node.get(last_key)
    if isinstance(existing, dict) and "value" in existing:
        existing["value"] = value
        existing["source"] = "user"
        existing["confidence"] = 1.0
    else:
        node[last_key] = value


DEMO_SPECS = [
    {
        "id": "demo-long-endurance-uav",
        "name": "长航时固定翼无人机",
        "overrides": {
            "aircraft.name": "长航时固定翼无人机",
            "fuselage.length": 8.0,
            "fuselage.max_diameter": 1.2,
            "wing.span": 18.0,
            "wing.root_chord": 1.8,
            "wing.tip_chord": 0.9,
            "wing.sweep": 2.0,
            "wing.dihedral": 3.0,
            "mission.cruise_speed": 120,
            "mission.payload": 10,
            "mission.priority": "endurance",
            "engine.count": 1,
        },
    },
    {
        "id": "demo-high-speed-recon",
        "name": "高速小型侦察无人机",
        "overrides": {
            "aircraft.name": "高速小型侦察无人机",
            "fuselage.length": 2.5,
            "fuselage.max_diameter": 0.4,
            "wing.span": 4.0,
            "wing.root_chord": 0.8,
            "wing.tip_chord": 0.4,
            "wing.sweep": 25.0,
            "wing.dihedral": 0.0,
            "mission.cruise_speed": 250,
            "mission.payload": 3,
            "mission.priority": "speed",
            "engine.count": 1,
        },
    },
    {
        "id": "demo-heavy-lift-uav",
        "name": "大载荷低速巡航无人机",
        "overrides": {
            "aircraft.name": "大载荷低速巡航无人机",
            "fuselage.length": 10.0,
            "fuselage.max_diameter": 2.0,
            "wing.span": 22.0,
            "wing.root_chord": 2.5,
            "wing.tip_chord": 1.5,
            "wing.sweep": 1.0,
            "wing.dihedral": 4.0,
            "mission.cruise_speed": 80,
            "mission.payload": 50,
            "mission.priority": "payload",
            "engine.count": 2,
        },
    },
]


def main() -> int:
    use_json = "--json" in sys.argv

    from services.api.app.schemas.aircraft_spec import AircraftSpec
    from services.api.app.services.job_runner import JobRunner
    from services.api.app.services.version_store import VersionStore
    from services.workers.cad_worker.openvsp_generator.backend_factory import get_cad_backend

    storage_root = PROJECT_ROOT / "storage"
    store = VersionStore(root=storage_root)
    backend = get_cad_backend()
    runner = JobRunner(store=store, backend=backend)

    results = []

    for demo in DEMO_SPECS:
        spec_dict = _base_spec()
        for path, value in demo["overrides"].items():
            _set(spec_dict, path, value)

        spec = AircraftSpec.model_validate(spec_dict)
        design_id = demo["id"]

        t0 = time.time()
        try:
            job = runner.generate(design_id=design_id, spec=spec)
            elapsed = time.time() - t0
            results.append({
                "id": design_id,
                "name": demo["name"],
                "status": job.status,
                "version_no": job.version_no,
                "elapsed_s": round(elapsed, 1),
            })
            if not use_json:
                print(f"  [{job.status.upper()}] {demo['name']} ({design_id}) — v{job.version_no} in {elapsed:.1f}s")
        except Exception as exc:
            elapsed = time.time() - t0
            results.append({
                "id": design_id,
                "name": demo["name"],
                "status": "failed",
                "error": str(exc),
                "elapsed_s": round(elapsed, 1),
            })
            if not use_json:
                print(f"  [FAIL] {demo['name']} ({design_id}) — {exc}")

    if use_json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        passed = sum(1 for r in results if r["status"] == "succeeded")
        print(f"\nDemo seeding complete: {passed}/{len(results)} succeeded")

    return 0


if __name__ == "__main__":
    sys.exit(main())
