from dataclasses import dataclass, field


@dataclass(frozen=True)
class GeometryBuildResult:
    name: str
    geom_id: str
    applied_parameters: dict[str, object] = field(default_factory=dict)
