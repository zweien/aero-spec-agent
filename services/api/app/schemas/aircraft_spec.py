from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, StrictStr, model_validator


Source = Literal["user", "inferred", "rule_default", "system_default"]


class ScalarBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit: str | None = None
    source: Source
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str | None = None
    source_text: str | None = None

    @model_validator(mode="after")
    def user_values_need_high_confidence(self) -> "ScalarBase":
        if self.source == "user" and self.confidence < 0.7:
            raise ValueError("user supplied values must have confidence >= 0.7")
        return self


class NumericScalar(ScalarBase):
    value: StrictFloat | StrictInt


class IntegerScalar(ScalarBase):
    value: StrictInt


class TextScalar(ScalarBase):
    value: StrictStr


Scalar = NumericScalar | IntegerScalar | TextScalar


class Aircraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: Literal["fixed_wing_uav"]
    layout: Literal["conventional"]


class Mission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cruise_speed: NumericScalar | None = None
    payload: NumericScalar | None = None
    priority: TextScalar | None = None


class Fuselage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    length: NumericScalar
    max_diameter: NumericScalar | None = None


class Wing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: TextScalar
    span: NumericScalar
    root_chord: NumericScalar
    tip_chord: NumericScalar
    sweep: NumericScalar | None = None
    dihedral: NumericScalar | None = None
    airfoil: TextScalar | None = None


class Tail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: TextScalar


class Engine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: IntegerScalar
    position: TextScalar | None = None


class AircraftSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["0.1"]
    aircraft: Aircraft
    mission: Mission = Field(default_factory=Mission)
    fuselage: Fuselage
    wing: Wing
    tail: Tail
    engine: Engine
