#!/usr/bin/env python3
"""Validate OpenVSP full pipeline: single-engine and twin-engine UAV.

Generates aircraft using OpenVspBackend and validates all output artifacts.
Graceful skip when OpenVSP is not available.

Usage: python scripts/validate_openvsp_pipeline.py [--json]

Exit codes: 0=pass/skip, 1=fail
"""

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def check_openvsp_available() -> bool:
    try:
        import openvsp  # noqa: F401
        return True
    except ImportError:
        return False


def load_twin_engine_spec():
    from services.api.app.services.spec_io import load_aircraft_spec
    return load_aircraft_spec(PROJECT_ROOT / "packages/aircraft-schema/examples/twin_engine_uav.yaml")


def make_single_engine_spec():
    """Create a single-engine variant from the twin-engine example."""
    import yaml
    from services.api.app.schemas.aircraft_spec import AircraftSpec

    with open(PROJECT_ROOT / "packages/aircraft-schema/examples/twin_engine_uav.yaml") as f:
        data = yaml.safe_load(f)

    data["aircraft"]["name"] = "validation_single_engine"
    data["engine"]["count"]["value"] = 1
    data["fuselage"]["length"]["value"] = 5.0
    data["wing"]["span"]["value"] = 8.0

    return AircraftSpec.model_validate(data)


def validate_artifacts(output_dir: Path, label: str) -> dict:
    """Validate that expected artifacts exist and are non-empty."""
    checks = {}
    required = ["aircraft.vsp3", "aircraft.glb"]
    optional = ["aircraft.step", "aircraft.obj"]
    metadata = ["generation_log.json", "validation_report.json"]

    for name in required + optional + metadata:
        p = output_dir / name
        if name in required:
            ok = p.exists() and p.stat().st_size > 0
            checks[name] = {"status": "pass" if ok else "FAIL", "size_kb": p.stat().st_size / 1024 if p.exists() else 0}
        elif name in optional:
            ok = p.exists() and p.stat().st_size > 0
            checks[name] = {"status": "pass" if ok else "skip", "size_kb": p.stat().st_size / 1024 if p.exists() else 0}
        else:
            if p.exists():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    checks[name] = {"status": "pass", "valid_json": True}
                    if name == "validation_report.json":
                        has_dm = "design_metrics" in data
                        checks[name]["has_design_metrics"] = has_dm
                except json.JSONDecodeError:
                    checks[name] = {"status": "FAIL", "valid_json": False}
            else:
                checks[name] = {"status": "FAIL", "valid_json": False}

    return checks


def run_validation() -> dict:
    from services.workers.cad_worker.openvsp_generator.backend import OpenVspBackend
    from services.workers.cad_worker.openvsp_generator.generate_aircraft import generate_aircraft

    results = {"openvsp_available": True, "cases": []}

    cases = [
        ("single_engine_uav", make_single_engine_spec()),
        ("twin_engine_uav", load_twin_engine_spec()),
    ]

    for label, spec in cases:
        with tempfile.TemporaryDirectory(prefix=f"openvsp_val_{label}_") as tmpdir:
            outdir = Path(tmpdir)
            backend = OpenVspBackend()
            result = generate_aircraft(spec, outdir, backend=backend)
            artifact_checks = validate_artifacts(outdir, label)
            results["cases"].append({
                "label": label,
                "status": "pass" if all(c["status"] != "FAIL" for c in artifact_checks.values()) else "fail",
                "artifacts": artifact_checks,
                "files": {k: str(v) for k, v in result.files.items()},
            })

    return results


def main() -> int:
    use_json = "--json" in sys.argv

    if not check_openvsp_available():
        msg = "OpenVSP not available — skipping validation"
        if use_json:
            print(json.dumps({"status": "skip", "reason": msg}))
        else:
            print(f"SKIP: {msg}")
        return 0

    try:
        results = run_validation()
    except Exception as exc:
        if use_json:
            print(json.dumps({"status": "fail", "error": str(exc)}))
        else:
            print(f"FAIL: {exc}")
        return 1

    if use_json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print("OpenVSP Pipeline Validation")
        print("=" * 60)
        for case in results["cases"]:
            print(f"\n  [{case['status'].upper()}] {case['label']}")
            for name, info in case["artifacts"].items():
                icon = "PASS" if info["status"] == "pass" else ("SKIP" if info["status"] == "skip" else "FAIL")
                extra = ""
                if "size_kb" in info and info["size_kb"] > 0:
                    extra = f" ({info['size_kb']:.1f} KB)"
                if "has_design_metrics" in info:
                    extra += f" design_metrics={'yes' if info['has_design_metrics'] else 'no'}"
                print(f"    [{icon}] {name}{extra}")

    all_pass = all(c["status"] == "pass" for c in results["cases"])
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
