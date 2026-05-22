#!/usr/bin/env python3
"""OpenVSP environment check script.

Verifies OpenVSP installation and capabilities for the aero-spec-agent CAD pipeline.
Run from project root: python scripts/check_openvsp_env.py
"""

import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, field


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    details: str = ""


results: list[CheckResult] = []


def check(name: str) -> bool:
    print(f"  Checking: {name}...", end=" ", flush=True)
    return True


def report(result: CheckResult) -> None:
    results.append(result)
    icon = "PASS" if result.passed else "FAIL"
    print(f"[{icon}] {result.message}")
    if result.details:
        for line in result.details.splitlines():
            print(f"         {line}")


def main() -> int:
    print("=" * 60)
    print("OpenVSP Environment Check")
    print("=" * 60)
    print()

    # 1. Check openvsp executable exists
    vsp_exe = shutil.which("openvsp") or shutil.which("vsp") or os.getenv("OPENVSP_EXE")
    if vsp_exe:
        report(CheckResult("executable", True, f"Found OpenVSP at: {vsp_exe}"))
    else:
        report(CheckResult("executable", False, "OpenVSP executable not found in PATH or OPENVSP_EXE"))
        _print_fallback()
        return 1

    # 2. Try importing openvsp Python module
    try:
        import vsp  # noqa: F401

        report(CheckResult("python_module", True, f"OpenVSP Python module available: {vsp}"))
    except ImportError:
        # Try alternative import
        try:
            import openvsp  # noqa: F401

            report(CheckResult("python_module", True, f"OpenVSP Python module available: {openvsp}"))
        except ImportError:
            report(CheckResult("python_module", False, "OpenVSP Python module not importable (vsp or openvsp)"))
            _print_fallback()
            return 1

    # 3. Initialize OpenVspBackend
    try:
        from services.workers.cad_worker.openvsp_generator.backend import OpenVspBackend

        backend = OpenVspBackend()
        report(CheckResult("backend_init", True, "OpenVspBackend initialized successfully"))
    except Exception as exc:
        report(CheckResult("backend_init", False, f"OpenVspBackend initialization failed: {exc}"))
        _print_fallback()
        return 1

    # 4. Check output directory writable
    try:
        tmpdir = tempfile.mkdtemp(prefix="openvsp_check_")
        test_file = os.path.join(tmpdir, "write_test")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        os.rmdir(tmpdir)
        report(CheckResult("output_dir", True, "Output directory writable"))
    except Exception as exc:
        report(CheckResult("output_dir", False, f"Output directory not writable: {exc}"))
        return 1

    # 5-8. Generate minimal test aircraft and export
    try:
        from services.api.app.schemas.aircraft_spec import AircraftSpec
        from services.workers.cad_worker.openvsp_generator.backend import CadArtifacts
    except Exception as exc:
        report(CheckResult("imports", False, f"Required imports failed: {exc}"))
        return 1

    # Create minimal spec
    try:
        spec_data = {
            "aircraft": {"name": "env_check_test", "type": "fixed_wing_uav"},
            "fuselage": {"length": {"value": 4.0, "unit": "m"}, "max_diameter": {"value": 0.6, "unit": "m"}},
            "wing": {
                "span": {"value": 6.0, "unit": "m"},
                "root_chord": {"value": 0.8, "unit": "m"},
                "tip_chord": {"value": 0.5, "unit": "m"},
                "sweep": {"value": 3.0, "unit": "deg"},
                "dihedral": {"value": 2.0, "unit": "deg"},
                "z_rel_location": {"value": 0.1},
            },
            "horizontal_tail": {
                "span": {"value": 2.0, "unit": "m"},
                "root_chord": {"value": 0.5, "unit": "m"},
                "tip_chord": {"value": 0.3, "unit": "m"},
            },
            "vertical_tail": {
                "span": {"value": 0.8, "unit": "m"},
                "root_chord": {"value": 0.5, "unit": "m"},
                "tip_chord": {"value": 0.3, "unit": "m"},
            },
            "engine": {"count": {"value": 1}, "type": "propeller"},
        }
        spec = AircraftSpec.model_validate(spec_data)
        report(CheckResult("spec_create", True, "Minimal test aircraft spec created"))
    except Exception as exc:
        report(CheckResult("spec_create", False, f"Failed to create test spec: {exc}"))
        return 1

    # Generate with OpenVSP
    try:
        outdir = tempfile.mkdtemp(prefix="openvsp_gen_")
        artifacts = backend.generate(spec, outdir)
        report(CheckResult("generate", True, "Test aircraft generated successfully"))
    except Exception as exc:
        report(CheckResult("generate", False, f"Generation failed: {exc}"))
        _cleanup(outdir)
        _print_fallback()
        return 1

    # Check individual artifacts
    _check_artifact("vsp3", artifacts.vsp3, "aircraft.vsp3")
    _check_artifact("step", artifacts.step, "aircraft.step", required=False)
    _check_artifact("glb", artifacts.glb, "aircraft.glb")

    _cleanup(outdir)

    # Summary
    print()
    print("=" * 60)
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("OpenVSP environment is ready for use.")
        return 0
    else:
        _print_fallback()
        return 1


def _check_artifact(name: str, path: "os.PathLike | None", expected_name: str, *, required: bool = True) -> None:
    from pathlib import Path

    if path is None:
        if required:
            report(CheckResult(name, False, f"{expected_name} not generated"))
        else:
            report(CheckResult(name, True, f"{expected_name} not available (optional)", "This format may not be supported"))
        return

    p = Path(path)
    if p.exists() and p.stat().st_size > 0:
        size_kb = p.stat().st_size / 1024
        report(CheckResult(name, True, f"{expected_name} generated ({size_kb:.1f} KB)"))
    else:
        if required:
            report(CheckResult(name, False, f"{expected_name} is empty or missing"))
        else:
            report(CheckResult(name, True, f"{expected_name} empty (optional)"))


def _cleanup(tmpdir: str) -> None:
    import shutil
    try:
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pass


def _print_fallback() -> None:
    print()
    print("FALLBACK: Set CAD_BACKEND=fake to use the fake CAD backend for testing.")
    print("The fake backend requires no OpenVSP installation.")


if __name__ == "__main__":
    sys.exit(main())
