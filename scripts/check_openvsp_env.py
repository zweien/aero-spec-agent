#!/usr/bin/env python3
"""OpenVSP environment check script.

Verifies OpenVSP installation and capabilities for the aero-spec-agent CAD pipeline.
Run from project root: python scripts/check_openvsp_env.py [--json]

Exit codes:
  0 - all checks passed
  2 - some checks failed (partial)
  3 - OpenVSP not available at all
"""

import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    details: str = ""


results: list[CheckResult] = []


def report(result: CheckResult) -> None:
    results.append(result)


def _print_human() -> None:
    for r in results:
        icon = "PASS" if r.passed else "FAIL"
        print(f"  [{icon}] {r.name}: {r.message}")
        if r.details:
            for line in r.details.splitlines():
                print(f"         {line}")


def _print_json() -> None:
    data = {
        "checks": [
            {"name": r.name, "passed": r.passed, "message": r.message, "details": r.details}
            for r in results
        ],
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "sys_path": sys.path,
        "python_version": sys.version,
    }
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _search_paths() -> list[str]:
    """Candidate directories where openvsp might live."""
    candidates: list[str] = []
    # Conda environments
    conda_prefix = os.getenv("CONDA_PREFIX")
    if conda_prefix:
        candidates += [conda_prefix, os.path.join(conda_prefix, "lib")]
    # Standard locations
    for d in ["/opt/openvsp", "/opt/OpenVSP", "/usr/local", "/usr"]:
        candidates.append(d)
    # PATH entries
    for d in os.getenv("PATH", "").split(os.pathsep):
        if d:
            candidates.append(d)
    # sys.path entries
    candidates += sys.path
    return candidates


def _find_executable() -> str | None:
    """Search for openvsp/vsp executable."""
    for name in ["openvsp", "vsp"]:
        found = shutil.which(name)
        if found:
            return found
    env_exe = os.getenv("OPENVSP_EXE")
    if env_exe and os.path.isfile(env_exe):
        return env_exe
    return None


def _get_version(vsp_module: object) -> str | None:
    """Try to get OpenVSP version string."""
    for attr in ("GetVersion", "get_version", "VERSION", "version"):
        fn = getattr(vsp_module, attr, None)
        if callable(fn):
            try:
                return str(fn())
            except Exception:
                pass
        elif isinstance(fn, str):
            return fn
    return None


def main() -> int:
    use_json = "--json" in sys.argv

    if not use_json:
        print("=" * 60)
        print("OpenVSP Environment Check")
        print("=" * 60)
        print()

    vsp_module = None
    fatal = False

    # 1. Executable
    exe = _find_executable()
    if exe:
        report(CheckResult("executable", True, f"Found: {exe}"))
    else:
        searched = _search_paths()
        report(CheckResult("executable", False, "OpenVSP executable not found",
                           f"Searched: PATH, /opt/openvsp, /usr/local, conda prefix.\n"
                           f"sys.path: {sys.path[:5]}..."))
        fatal = True

    # 2. Python module import
    for mod_name in ("vsp", "openvsp"):
        try:
            vsp_module = __import__(mod_name)
            report(CheckResult("python_module", True, f"Module '{mod_name}' imported"))
            break
        except ImportError:
            continue
    if vsp_module is None:
        report(CheckResult("python_module", False, "Cannot import 'vsp' or 'openvsp'",
                           f"sys.path entries: {sys.path[:5]}...\n"
                           "Install OpenVSP with Python bindings or add to PYTHONPATH."))
        fatal = True

    # 3. Version detection
    if vsp_module is not None:
        ver = _get_version(vsp_module)
        if ver:
            report(CheckResult("version", True, f"OpenVSP version: {ver}"))
        else:
            report(CheckResult("version", True, "Version info not available (non-blocking)"))

    # 4. Backend initialization
    backend = None
    if vsp_module is not None:
        try:
            from services.workers.cad_worker.openvsp_generator.backend import OpenVspBackend
            backend = OpenVspBackend(vsp_module=vsp_module)
            report(CheckResult("backend_init", True, "OpenVspBackend initialized"))
        except Exception as exc:
            report(CheckResult("backend_init", False, f"Backend init failed: {exc}"))
            fatal = True

    # 5. Output directory writable
    tmpdir: str | None = None
    try:
        tmpdir = tempfile.mkdtemp(prefix="openvsp_check_")
        test_file = os.path.join(tmpdir, "write_test")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        report(CheckResult("output_dir", True, f"Temp dir writable: {tmpdir}"))
    except Exception as exc:
        report(CheckResult("output_dir", False, f"Output dir not writable: {exc}"))
        fatal = True

    # Early exit if critical checks failed
    if fatal:
        _finalize(use_json)
        return 3

    # 6. Generate minimal test aircraft
    assert backend is not None and tmpdir is not None
    artifacts = None
    try:
        from services.api.app.schemas.aircraft_spec import AircraftSpec

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
        report(CheckResult("spec_create", True, "Test spec created"))

        artifacts = backend.generate(spec, Path(tmpdir))
        report(CheckResult("generate", True, "Test aircraft generated"))
    except Exception as exc:
        report(CheckResult("generate", False, f"Generation failed: {exc}",
                           "Set CAD_BACKEND=fake for testing without OpenVSP."))
        _cleanup(tmpdir)
        _finalize(use_json)
        return 2

    # 7. Artifact checks
    _check_artifact("vsp3", artifacts.vsp3, "aircraft.vsp3")
    _check_artifact("glb", artifacts.glb, "aircraft.glb")
    _check_artifact("step", artifacts.step, "aircraft.step", required=False)

    _cleanup(tmpdir)
    _finalize(use_json)

    failed = sum(1 for r in results if not r.passed)
    return 0 if failed == 0 else 2


def _check_artifact(name: str, path: "os.PathLike | None", expected_name: str, *, required: bool = True) -> None:
    if path is None:
        if required:
            report(CheckResult(name, False, f"{expected_name} not generated"))
        else:
            report(CheckResult(name, True, f"{expected_name} not available (optional)"))
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


def _cleanup(tmpdir: str | None) -> None:
    if tmpdir:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _finalize(use_json: bool) -> None:
    if use_json:
        _print_json()
        return

    _print_human()
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    print()
    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("OpenVSP environment is ready.")
    else:
        print("Set CAD_BACKEND=fake for testing without OpenVSP.")


if __name__ == "__main__":
    sys.exit(main())
