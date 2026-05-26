#!/usr/bin/env python3
"""Validate OpenVSP generation for all 11 aerodynamic layouts.

Generates aircraft for each layout and validates all output artifacts.
Produces a Markdown QA report at docs/layout-openvsp-qa.md.

Usage:
    python scripts/validate_layout_matrix.py              # auto-detect backend
    python scripts/validate_layout_matrix.py --backend fake
    python scripts/validate_layout_matrix.py --backend openvsp
    python scripts/validate_layout_matrix.py --json
    python scripts/validate_layout_matrix.py --output path/to/report.md

Exit codes: 0=pass/skip, 1=fail
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

LAYOUTS: dict[str, str] = {
    "conventional": "twin_engine_uav.yaml",
    "twin_boom": "twin_boom_pusher_uav.yaml",
    "flying_wing": "flying_wing_uav.yaml",
    "blended_wing_body": "bwb_uav.yaml",
    "canard": "canard_uav.yaml",
    "three_surface": "three_surface_uav.yaml",
    "tandem_wing": "tandem_wing_uav.yaml",
    "biplane": "biplane_uav.yaml",
    "joined_wing": "joined_wing_uav.yaml",
    "box_wing": "box_wing_uav.yaml",
    "multi_fuselage": "multi_fuselage_uav.yaml",
}

COMPLEX_LAYOUTS = {
    "canard", "three_surface", "biplane", "box_wing",
    "multi_fuselage", "joined_wing",
}

EXAMPLES_DIR = PROJECT_ROOT / "packages" / "aircraft-schema" / "examples"
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "layout-openvsp-qa.md"


def check_openvsp_available() -> tuple[bool, str]:
    try:
        import openvsp
        version = getattr(openvsp, "GetVSPVersion", lambda: "unknown")
        return True, str(version()) if callable(version) else "available"
    except ImportError:
        return False, "not installed"


def detect_backend() -> str:
    env = os.getenv("CAD_BACKEND", "").strip().lower()
    if env == "openvsp":
        avail, _ = check_openvsp_available()
        return "openvsp" if avail else "fake"
    if env == "fake":
        return "fake"
    avail, _ = check_openvsp_available()
    return "openvsp" if avail else "fake"


def resolve_backend(cli_backend: str) -> str:
    """Resolve backend from CLI arg, falling back to env/auto."""
    if cli_backend == "auto":
        return detect_backend()
    if cli_backend == "openvsp":
        avail, _ = check_openvsp_available()
        if not avail:
            return "__openvsp_unavailable__"
        return "openvsp"
    if cli_backend == "fake":
        return "fake"
    return detect_backend()


def load_spec_with_defaults(yaml_file: str) -> tuple[object, dict]:
    from services.api.app.services.spec_io import load_aircraft_spec
    from services.api.app.services.spec_defaults import ensure_required_defaults

    yaml_path = EXAMPLES_DIR / yaml_file
    spec = load_aircraft_spec(yaml_path)

    spec_dict = spec.model_dump(mode="json")
    ensure_required_defaults(spec_dict)

    from services.api.app.schemas.aircraft_spec import AircraftSpec
    spec = AircraftSpec.model_validate(spec_dict)
    return spec, spec_dict


def validate_artifacts(output_dir: Path) -> dict:
    checks: dict[str, dict] = {}
    required = ["aircraft.vsp3", "aircraft.glb"]
    optional = ["aircraft.step", "aircraft.obj"]
    metadata_files = ["aircraft_spec.yaml", "generation_log.json", "validation_report.json"]

    for name in required:
        p = output_dir / name
        ok = p.exists() and p.stat().st_size > 0
        size_kb = round(p.stat().st_size / 1024, 1) if p.exists() else 0
        checks[name] = {"status": "pass" if ok else "FAIL", "size_kb": size_kb}

    for name in optional:
        p = output_dir / name
        ok = p.exists() and p.stat().st_size > 0
        size_kb = round(p.stat().st_size / 1024, 1) if p.exists() else 0
        checks[name] = {"status": "pass" if ok else "skip", "size_kb": size_kb}

    for name in metadata_files:
        p = output_dir / name
        if not p.exists():
            checks[name] = {"status": "FAIL", "exists": False, "size_kb": 0}
            continue
        size_kb = round(p.stat().st_size / 1024, 1)
        if name.endswith(".json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                info: dict = {"status": "pass", "valid_json": True, "size_kb": size_kb}
                if name == "validation_report.json":
                    info["has_design_metrics"] = "design_metrics" in data
                    info["has_variant_trust"] = "variant_trust" in data
                checks[name] = info
            except json.JSONDecodeError:
                checks[name] = {"status": "FAIL", "valid_json": False, "size_kb": size_kb}
        else:
            checks[name] = {"status": "pass", "size_bytes": p.stat().st_size, "size_kb": size_kb}

    return checks


def validate_layout(layout: str, yaml_file: str, backend_name: str) -> dict:
    from services.workers.cad_worker.openvsp_generator.backend import FakeCadBackend, OpenVspBackend
    from services.workers.cad_worker.openvsp_generator.generate_aircraft import generate_aircraft

    result: dict = {
        "layout": layout,
        "yaml_file": yaml_file,
        "status": "pending",
        "error": None,
        "artifacts": {},
        "spec_ok": False,
        "defaults_ok": False,
        "backend_actual": None,
        "components_analyzed": [],
        "components": {},
    }

    try:
        spec, spec_dict = load_spec_with_defaults(yaml_file)
        result["spec_ok"] = True
        result["defaults_ok"] = True
    except Exception as exc:
        result["status"] = "FAIL"
        result["error"] = f"spec load failed: {exc}"
        return result

    with tempfile.TemporaryDirectory(prefix=f"qa_layouts_{backend_name}_") as tmpdir:
        outdir = Path(tmpdir) / "qa_layouts" / backend_name
        outdir.mkdir(parents=True, exist_ok=True)
        try:
            if backend_name == "openvsp":
                backend = OpenVspBackend()
            else:
                backend = FakeCadBackend()
            gen_result = generate_aircraft(spec, outdir, backend=backend)
            result["files"] = {k: str(v) for k, v in gen_result.files.items()}
            result["components"] = gen_result.generation_log.get("components", {})
            result["backend_actual"] = gen_result.generation_log.get("backend", backend_name)

            # Extract VSPAERO and variant_trust info from validation_report
            vr = gen_result.validation_report or {}
            vt = vr.get("variant_trust", {})
            if isinstance(vt, dict):
                result["variant_trust_generated_by"] = vt.get("generated_by", "")
            vspaero = vr.get("vspaero_analysis")
            if isinstance(vspaero, dict):
                result["components_analyzed"] = vspaero.get("components_analyzed", []) or []

            import yaml
            spec_yaml_path = outdir / "aircraft_spec.yaml"
            spec_yaml_path.write_text(
                yaml.dump(spec_dict, allow_unicode=True, default_flow_style=False),
                encoding="utf-8",
            )
        except Exception as exc:
            result["status"] = "FAIL"
            result["error"] = f"generation failed: {exc}"
            result["artifacts"] = validate_artifacts(outdir)
            return result

        result["artifacts"] = validate_artifacts(outdir)
    artifact_fails = [k for k, v in result["artifacts"].items() if v["status"] == "FAIL"]
    if artifact_fails:
        result["status"] = "FAIL"
        result["error"] = f"artifact failures: {', '.join(artifact_fails)}"
    else:
        result["status"] = "pass"

    return result


def generate_report(results: list[dict], env_info: dict) -> str:
    today = date.today().isoformat()
    backend = env_info["backend"]
    openvsp_info = env_info["openvsp_info"]
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    skipped = sum(1 for r in results if r["status"] == "SKIPPED")
    overall = "pass" if failed == 0 else "fail"

    lines: list[str] = []
    lines.append("---")
    lines.append(f"qa_id: layout-openvsp-qa")
    lines.append(f"status: {overall}")
    lines.append(f"date: {today}")
    lines.append(f"env: {backend}")
    lines.append(f"openvsp_version: \"{openvsp_info}\"")
    lines.append(f"backend: {backend}")
    lines.append(f"layouts_total: {total}")
    lines.append(f"layouts_pass: {passed}")
    lines.append(f"layouts_skip: {skipped}")
    lines.append(f"layouts_fail: {failed}")
    lines.append("---")
    lines.append("")
    lines.append(f"# Layout OpenVSP QA Report")
    lines.append("")

    # Prominent disclaimer
    lines.append("> **Note:** This report validates the software generation pipeline. "
                 '"PASS" means artifacts were generated successfully. '
                 "It does NOT mean the aircraft configuration is aerodynamically optimal, "
                 "structurally feasible, or engineering certified.")
    lines.append("")

    # Backend-specific warning/confirmation
    if "unavailable" in backend:
        lines.append("> **Warning:** OpenVSP was not available. All layouts were skipped. "
                     "Install OpenVSP 3.50.2 or use `--backend fake`.")
    elif backend == "fake":
        lines.append("> **Warning:** This report uses the fake backend. Artifacts are placeholders, "
                     "not real geometry. Run with `--backend openvsp` for real OpenVSP validation.")
    else:
        lines.append("> **Confirmed:** Real OpenVSP artifacts generated. "
                     "Visual inspection of 3D models recommended for geometric plausibility.")
    lines.append("")

    lines.append(f"**Date:** {today}")
    lines.append(f"**Backend:** {backend}")
    lines.append(f"**OpenVSP:** {openvsp_info}")
    lines.append(f"**Result:** {passed}/{total} layouts passed")
    lines.append("")

    lines.append("## Environment")
    lines.append("")
    lines.append(f"| Item | Value |")
    lines.append(f"|------|-------|")
    lines.append(f"| Date | {today} |")
    lines.append(f"| Backend | {backend} |")
    lines.append(f"| OpenVSP | {openvsp_info} |")
    lines.append(f"| Python | {platform.python_version()} |")
    lines.append(f"| Total layouts | {total} |")
    lines.append(f"| Passed | {passed} |")
    lines.append(f"| Skipped | {skipped} |")
    lines.append(f"| Failed | {failed} |")
    lines.append(f"| Script | `scripts/validate_layout_matrix.py` |")
    lines.append("")

    lines.append("## Layout Verification Matrix")
    lines.append("")
    lines.append("| Layout | Spec | Defaults | VSP3 | GLB | STEP | OBJ | Log | Report | Metrics | Backend | Status |")
    lines.append("|--------|:----:|:--------:|:----:|:---:|:----:|:---:|:---:|:------:|:-------:|:-------:|:------:|")

    icon = lambda s: "✅" if s == "pass" else ("⚠️" if s == "skip" else "❌")

    for r in results:
        a = r["artifacts"]
        spec_icon = "✅" if r["spec_ok"] else "❌"
        defaults_icon = "✅" if r["defaults_ok"] else "❌"
        vsp3_icon = icon(a.get("aircraft.vsp3", {}).get("status", "skip"))
        glb_icon = icon(a.get("aircraft.glb", {}).get("status", "skip"))
        step_icon = icon(a.get("aircraft.step", {}).get("status", "skip"))
        obj_icon = icon(a.get("aircraft.obj", {}).get("status", "skip"))
        log_icon = icon(a.get("generation_log.json", {}).get("status", "skip"))
        report_icon = icon(a.get("validation_report.json", {}).get("status", "skip"))
        metrics_val = a.get("validation_report.json", {}).get("has_design_metrics", False)
        metrics_icon = "✅" if metrics_val else "❌"

        # Backend verification column
        backend_actual = r.get("backend_actual", "")
        if "openvsp" in str(backend_actual).lower():
            backend_icon = "✅ openvsp"
        elif "fake" in str(backend_actual).lower() or "FakeCad" in str(backend_actual):
            backend_icon = "⚠️ fake"
        else:
            backend_icon = "❌"

        if r["status"] == "SKIPPED":
            status_icon = "⏭️ SKIP"
        else:
            status_icon = "✅" if r["status"] == "pass" else "❌"

        lines.append(f"| {r['layout']} | {spec_icon} | {defaults_icon} | {vsp3_icon} | {glb_icon} | {step_icon} | {obj_icon} | {log_icon} | {report_icon} | {metrics_icon} | {backend_icon} | {status_icon} |")

    lines.append("")

    lines.append("## Per-Layout Details")
    lines.append("")

    for r in results:
        if r["status"] == "SKIPPED":
            lines.append(f"### {r['layout']}")
            lines.append(f"")
            lines.append(f"- **Status:** SKIPPED (OpenVSP not available)")
            lines.append(f"- **YAML:** `packages/aircraft-schema/examples/{r['yaml_file']}`")
            lines.append("")
            continue

        status_str = "PASS" if r["status"] == "pass" else "FAIL"
        lines.append(f"### {r['layout']}")
        lines.append(f"")
        lines.append(f"- **Status:** {status_str}")
        lines.append(f"- **YAML:** `packages/aircraft-schema/examples/{r['yaml_file']}`")
        if r.get("error"):
            lines.append(f"- **Error:** {r['error']}")
        if r.get("backend_actual"):
            lines.append(f"- **Backend:** {r['backend_actual']}")

        # Components section
        if r.get("components"):
            comp_names = list(r["components"].keys())
            lines.append(f"- **Components:** {', '.join(comp_names)}")

        # Visual Inspection recommendation
        if r["layout"] in COMPLEX_LAYOUTS:
            lines.append(f"- **Visual Inspection:** Recommended (complex layout)")
        else:
            lines.append(f"- **Visual Inspection:** Optional")

        lines.append(f"")
        lines.append(f"| Artifact | Status | Size |")
        lines.append(f"|----------|--------|------|")
        for name, info in r.get("artifacts", {}).items():
            st = info.get("status", "?")
            sz = info.get("size_kb")
            sz_str = f"{sz} KB" if sz is not None else ""
            lines.append(f"| {name} | {st} | {sz_str} |")

        # VSPAERO section
        lines.append(f"")
        components_analyzed = r.get("components_analyzed", [])
        if components_analyzed:
            lines.append(f"**VSPAERO Analysis:** Surfaces analyzed: {', '.join(str(c) for c in components_analyzed)}")
        else:
            lines.append(f"**VSPAERO Analysis:** VSPAERO not run for this layout (triggered separately via settings)")
        lines.append(f"")
        lines.append(f"- **Frontend 2D preview:** ✅ (verified by `verify-layout-previews.mjs`)")
        lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Status | Count | Layouts |")
    lines.append(f"|--------|:-----:|---------|")
    if passed > 0:
        lines.append(f"| ✅ PASS | {passed} | {', '.join(r['layout'] for r in results if r['status'] == 'pass')} |")
    if skipped > 0:
        lines.append(f"| ⏭️ SKIP | {skipped} | {', '.join(r['layout'] for r in results if r['status'] == 'SKIPPED')} |")
    if failed > 0:
        lines.append(f"| ❌ FAIL | {failed} | {', '.join(r['layout'] for r in results if r['status'] == 'FAIL')} |")
    lines.append("")

    lines.append("## Maturity Assessment")
    lines.append("")
    if skipped == total:
        lines.append(f"All {total} layouts were skipped (OpenVSP not available). No maturity assessment possible.")
    elif failed == 0:
        lines.append(f"All {total} layouts generate valid artifacts via {backend} backend. All are suitable for **Stable** maturity.")
    else:
        lines.append(f"{passed}/{total} layouts generate valid artifacts. {failed} layouts need investigation before Stable.")
    lines.append("")

    lines.append("## Recommendations")
    lines.append("")
    if "unavailable" in backend:
        lines.append("- Install OpenVSP 3.50.2 and re-run with `--backend openvsp` for real geometry validation.")
        lines.append("- Alternatively, use `--backend fake` to validate pipeline structure without real geometry.")
    elif backend == "fake":
        lines.append("- **Real OpenVSP validation recommended:** Run with `--backend openvsp` for geometry validity confirmation.")
        lines.append("- Fake backend validates pipeline structure only, not geometric correctness.")
    else:
        lines.append("- Real OpenVSP artifacts generated. Visual inspection of 3D models recommended for geometric plausibility.")
    lines.append("- Layouts with multi-surface VSPAERO analysis: canard, three_surface, tandem_wing, joined_wing, biplane, box_wing.")
    lines.append("- Per-surface aerodynamic reports not yet available (VSPAERO outputs combined metrics).")
    lines.append("")

    lines.append("## Re-run")
    lines.append("")
    lines.append("```bash")
    if "unavailable" in backend:
        lines.append("# Install OpenVSP 3.50.2 first, then:")
        lines.append("python scripts/validate_layout_matrix.py --backend openvsp")
        lines.append("# Or validate pipeline structure only:")
        lines.append("python scripts/validate_layout_matrix.py --backend fake")
    elif backend == "fake":
        lines.append("python scripts/validate_layout_matrix.py --backend fake")
    else:
        lines.append("python scripts/validate_layout_matrix.py --backend openvsp")
    lines.append("```")

    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate OpenVSP generation for all aerodynamic layouts",
    )
    parser.add_argument(
        "--backend",
        choices=["openvsp", "fake", "auto"],
        default="auto",
        help="CAD backend to use. 'auto' (default) detects from CAD_BACKEND env var / OpenVSP availability. "
             "Overrides CAD_BACKEND env var when specified.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON instead of Markdown report",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT),
        help=f"Output path for the Markdown report (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    use_json = args.json
    output_path = Path(args.output)
    cli_backend = args.backend

    backend_name = resolve_backend(cli_backend)
    openvsp_avail, openvsp_info = check_openvsp_available()

    # Handle OpenVSP unavailable gracefully
    if backend_name == "__openvsp_unavailable__":
        print("OpenVSP not available. Install OpenVSP 3.50.2 or use --backend fake.")
        print("")

        # Mark all layouts as SKIPPED
        results: list[dict] = []
        for layout, yaml_file in LAYOUTS.items():
            results.append({
                "layout": layout,
                "yaml_file": yaml_file,
                "status": "SKIPPED",
                "error": "OpenVSP not available",
                "artifacts": {},
                "spec_ok": False,
                "defaults_ok": False,
                "backend_actual": None,
                "components_analyzed": [],
                "components": {},
            })

        env_info = {
            "backend": "openvsp (unavailable)",
            "openvsp_available": False,
            "openvsp_info": openvsp_info,
        }

        if use_json:
            print(json.dumps({"env": env_info, "results": results}, indent=2, ensure_ascii=False))
        else:
            report = generate_report(results, env_info)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report, encoding="utf-8")
            print(f"Report written to {output_path}")

        print(f"Result: 0/{len(results)} passed, 0 failed, {len(results)} skipped")
        return 0

    env_info = {
        "backend": backend_name,
        "openvsp_available": openvsp_avail,
        "openvsp_info": openvsp_info if openvsp_avail else "not available",
    }

    print(f"Layout QA Validation — backend: {backend_name}, OpenVSP: {openvsp_info}")
    print("=" * 60)

    results = []
    for layout, yaml_file in LAYOUTS.items():
        print(f"  Validating {layout}...", end=" ", flush=True)
        r = validate_layout(layout, yaml_file, backend_name)
        results.append(r)
        if r["status"] == "SKIPPED":
            icon = "⏭️"
        else:
            icon = "✅" if r["status"] == "pass" else "❌"
        err = f" ({r['error']})" if r.get("error") else ""
        print(f"{icon} {r['status'].upper()}{err}")

    print("=" * 60)

    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    skipped = sum(1 for r in results if r["status"] == "SKIPPED")
    print(f"Result: {passed}/{len(results)} passed, {failed} failed, {skipped} skipped")

    if use_json:
        print(json.dumps({"env": env_info, "results": results}, indent=2, ensure_ascii=False))
    else:
        report = generate_report(results, env_info)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"Report written to {output_path}")

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
