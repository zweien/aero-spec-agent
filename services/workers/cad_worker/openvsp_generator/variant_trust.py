"""Variant trust/confidence calculation for design variants.

Computes a VariantTrust assessment based on generation context:
backend type, metrics source, defaulted fields, geometry and analysis status.
"""

from dataclasses import dataclass, field


@dataclass
class VariantTrust:
    backend: str
    metrics_source: str
    defaulted_parameter_count: int
    warnings: list[str] = field(default_factory=list)
    confidence_level: str = "unknown"
    confidence_reasons: list[str] = field(default_factory=list)
    generated_by: str = ""
    has_real_geometry: bool = False
    has_aero_analysis: bool = False

    def to_dict(self) -> dict:
        return {
            "backend": self.backend,
            "metrics_source": self.metrics_source,
            "defaulted_parameter_count": self.defaulted_parameter_count,
            "warnings": self.warnings,
            "confidence_level": self.confidence_level,
            "confidence_reasons": self.confidence_reasons,
            "generated_by": self.generated_by,
            "has_real_geometry": self.has_real_geometry,
            "has_aero_analysis": self.has_aero_analysis,
        }


def compute_variant_trust(
    *,
    backend_name: str,
    metrics_source: str,
    defaulted_parameter_count: int,
    warnings: list[str] | None = None,
    has_real_geometry: bool = False,
    has_aero_analysis: bool = False,
) -> VariantTrust:
    """Compute variant trust/confidence based on generation context.

    Rules:
    - Fake CAD always gets "low" confidence
    - client_heuristic metrics always gets "low"
    - >=5 defaulted parameters gets "low"
    - "high" only when: openvsp + backend_design_metrics + aero + <3 defaulted
    - Otherwise "medium"
    """
    warnings = warnings or []
    reasons: list[str] = []
    level = "medium"

    generated_by = "fake_cad" if backend_name == "fake" else "openvsp"

    # Fake CAD always low
    if backend_name == "fake":
        level = "low"
        reasons.append("Fake CAD 生成占位几何，非真实工程模型")

    # Client heuristic always low
    if metrics_source == "client_heuristic":
        level = "low"
        if "client_heuristic" not in " ".join(reasons):
            reasons.append("指标来自客户端临时估算")

    # Too many defaults
    if defaulted_parameter_count >= 5:
        level = "low"
        reasons.append(f"{defaulted_parameter_count} 个参数为默认补全")

    # High confidence: strict requirements
    if backend_name == "openvsp" and level != "low":
        if metrics_source == "backend_design_metrics" and has_aero_analysis and defaulted_parameter_count < 3:
            level = "high"
            reasons.append("OpenVSP 真实几何 + 后端指标 + 气动分析")
        elif not has_aero_analysis:
            reasons.append("缺少气动分析")
        if defaulted_parameter_count >= 3:
            reasons.append(f"{defaulted_parameter_count} 个默认参数")

    return VariantTrust(
        backend=backend_name,
        metrics_source=metrics_source,
        defaulted_parameter_count=defaulted_parameter_count,
        warnings=warnings,
        confidence_level=level,
        confidence_reasons=reasons,
        generated_by=generated_by,
        has_real_geometry=has_real_geometry,
        has_aero_analysis=has_aero_analysis,
    )
