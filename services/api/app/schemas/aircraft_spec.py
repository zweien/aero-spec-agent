from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Source = Literal["user", "inferred", "rule_default", "system_default"]


class Scalar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float | int | str
    unit: str | None = None
    source: Source
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str | None = None
    source_text: str | None = None

    @model_validator(mode="after")
    def user_values_need_high_confidence(self) -> "Scalar":
        if self.source == "user" and self.confidence < 0.7:
            raise ValueError("user supplied values must have confidence >= 0.7")
        return self


class Aircraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: Literal["fixed_wing_uav"]
    layout: Literal["conventional"]


class Mission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cruise_speed: Scalar | None = None
    payload: Scalar | None = None
    priority: Scalar | None = None


class Fuselage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    length: Scalar
    max_diameter: Scalar | None = None


class Wing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: Scalar
    span: Scalar
    root_chord: Scalar
    tip_chord: Scalar
    sweep: Scalar | None = None
    dihedral: Scalar | None = None
    airfoil: Scalar | None = None


class Tail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Scalar


class Engine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: Scalar
    position: Scalar | None = None


class AircraftSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["0.1"]
    aircraft: Aircraft
    mission: Mission = Field(default_factory=Mission)
    fuselage: Fuselage
    wing: Wing
    tail: Tail
    engine: Engine
