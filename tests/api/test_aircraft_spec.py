from copy import deepcopy
from pathlib import Path

import pytest

from services.api.app.services.spec_io import load_aircraft_spec


EXAMPLE = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml")


def valid_spec_data():
    return {
        "schema_version": "0.1",
        "aircraft": {"name": "typed", "type": "fixed_wing_uav", "layout": "conventional"},
        "mission": {},
        "fuselage": {"length": {"value": 7, "unit": "m", "source": "user", "confidence": 1}},
        "wing": {
            "position": {"value": "high", "source": "user", "confidence": 1},
            "span": {"value": 12, "unit": "m", "source": "user", "confidence": 1},
            "root_chord": {"value": 1.2, "unit": "m", "source": "rule_default", "confidence": 0.8},
            "tip_chord": {"value": 0.6, "unit": "m", "source": "rule_default", "confidence": 0.8},
        },
        "tail": {"type": {"value": "conventional", "source": "user", "confidence": 1}},
        "engine": {"count": {"value": 2, "source": "user", "confidence": 1}},
    }


def test_loads_example_spec_with_sources():
    spec = load_aircraft_spec(EXAMPLE)

    assert spec.wing.span.value == 12.0
    assert spec.wing.span.unit == "m"
    assert spec.wing.span.source == "user"
    assert spec.engine.count.value == 2
    assert spec.tail.type.value == "conventional"


def test_rejects_low_confidence_user_value():
    with pytest.raises(ValueError, match="confidence"):
        load_aircraft_spec(
            {
                "schema_version": "0.1",
                "aircraft": {"name": "bad", "type": "fixed_wing_uav", "layout": "conventional"},
                "mission": {},
                "fuselage": {"length": {"value": 7, "unit": "m", "source": "user", "confidence": 1}},
                "wing": {
                    "position": {"value": "high", "source": "user", "confidence": 0.5},
                    "span": {"value": 12, "unit": "m", "source": "user", "confidence": 1},
                    "root_chord": {"value": 1.2, "unit": "m", "source": "rule_default", "confidence": 0.8},
                    "tip_chord": {"value": 0.6, "unit": "m", "source": "rule_default", "confidence": 0.8},
                },
                "tail": {"type": {"value": "conventional", "source": "user", "confidence": 1}},
                "engine": {"count": {"value": 2, "source": "user", "confidence": 1}},
            }
        )


def test_rejects_text_wing_span_value():
    data = deepcopy(valid_spec_data())
    data["wing"]["span"]["value"] = "not-a-number"

    with pytest.raises(ValueError, match="value"):
        load_aircraft_spec(data)


def test_rejects_text_engine_count_value():
    data = deepcopy(valid_spec_data())
    data["engine"]["count"]["value"] = "two"

    with pytest.raises(ValueError, match="value"):
        load_aircraft_spec(data)
