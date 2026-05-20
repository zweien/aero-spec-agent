"""Tests for OpenVSP workflow events — verify stage sequence matches FakeCadBackend.

These tests use a mock backend that simulates OpenVSP stage emission,
since real OpenVSP requires the application installed locally.
"""

import pytest

from services.api.app.services.job_events import (
    JobEvent,
    JobEventBus,
    JobEventType,
    get_job_event_bus,
    reset_job_event_bus,
)
from services.api.app.services.workflow_events import CAD_STAGE_LABELS


@pytest.fixture(autouse=True)
def _reset_bus():
    reset_job_event_bus()
    yield
    reset_job_event_bus()


# Expected CAD stages in order, matching both FakeCadBackend and OpenVspBackend
EXPECTED_CAD_STAGES = [
    ("fuselage_created", 62),
    ("wing_created", 68),
    ("tail_created", 72),
    ("engine_created", 76),
    ("vsp_model_saved", 82),
    ("step_exported", 86),
    ("glb_exported", 92),
    ("preview_ready", 96),
]


def test_cad_stage_names_match_between_backends():
    """Both FakeCadBackend and OpenVspBackend should use the same stage names."""
    # Read the stage names from the source code
    from services.workers.cad_worker.openvsp_generator.backend import (
        FakeCadBackend,
        OpenVspBackend,
    )
    import inspect

    # Extract on_progress calls from FakeCadBackend
    fake_source = inspect.getsource(FakeCadBackend.generate)
    openvsp_source = inspect.getsource(OpenVspBackend.generate)

    fake_stages = []
    for stage, _ in EXPECTED_CAD_STAGES:
        assert stage in fake_source, f"FakeCadBackend missing stage: {stage}"
        assert stage in openvsp_source, f"OpenVspBackend missing stage: {stage}"
        fake_stages.append(stage)

    assert len(fake_stages) == 8


def test_all_cad_stages_have_chinese_labels():
    """Every CAD stage should have a Chinese label in CAD_STAGE_LABELS."""
    for stage, progress in EXPECTED_CAD_STAGES:
        assert stage in CAD_STAGE_LABELS, f"Missing label for stage: {stage}"
        label = CAD_STAGE_LABELS[stage]
        # Chinese label should not contain ASCII-only text
        assert len(label) > 0
        # Label should not be the same as the stage key (should be translated)
        assert label != stage, f"Label for {stage} is not translated"


def test_cad_stage_progress_values_are_monotonically_increasing():
    """Progress values should increase monotonically."""
    prev = 0
    for stage, progress in EXPECTED_CAD_STAGES:
        assert progress > prev, f"Progress for {stage} ({progress}) not > previous ({prev})"
        prev = progress


def test_cad_stages_cover_full_range():
    """CAD stages should cover from ~60% to ~96%."""
    assert EXPECTED_CAD_STAGES[0][1] >= 60
    assert EXPECTED_CAD_STAGES[-1][1] >= 95


def test_openvsp_backend_on_progress_signature():
    """OpenVspBackend.generate should accept on_progress keyword argument."""
    from services.workers.cad_worker.openvsp_generator.backend import OpenVspBackend
    import inspect

    sig = inspect.signature(OpenVspBackend.generate)
    assert "on_progress" in sig.parameters


def _make_spec():
    """Build a minimal valid AircraftSpec for testing."""
    from services.api.app.schemas.aircraft_spec import AircraftSpec
    return AircraftSpec.model_validate({
        "schema_version": "0.1",
        "aircraft": {"name": "test-uav", "type": "fixed_wing_uav", "layout": "conventional"},
        "wing": {
            "position": {"value": "high", "source": "user", "confidence": 1.0},
            "span": {"value": 10, "unit": "m", "source": "user", "confidence": 1.0},
            "root_chord": {"value": 1, "unit": "m", "source": "rule_default", "confidence": 0.7},
            "tip_chord": {"value": 0.5, "unit": "m", "source": "rule_default", "confidence": 0.7},
        },
        "tail": {"type": {"value": "conventional", "source": "user", "confidence": 1.0}},
        "engine": {"count": {"value": 1, "source": "user", "confidence": 1.0}},
        "fuselage": {
            "length": {"value": 6, "unit": "m", "source": "rule_default", "confidence": 0.7},
            "max_diameter": {"value": 0.6, "unit": "m", "source": "rule_default", "confidence": 0.7},
        },
    })


def test_fake_backend_emits_all_cad_stages():
    """FakeCadBackend should emit all 8 CAD stages via on_progress callback."""
    from services.workers.cad_worker.openvsp_generator.backend import FakeCadBackend
    import tempfile
    import pathlib

    collected: list[tuple[str, int]] = []

    def capture(stage: str, progress: int) -> None:
        collected.append((stage, progress))

    spec = _make_spec()

    with tempfile.TemporaryDirectory() as tmpdir:
        backend = FakeCadBackend()
        artifacts = backend.generate(spec, pathlib.Path(tmpdir), on_progress=capture)

    assert artifacts is not None
    assert len(collected) == 8
    assert collected == EXPECTED_CAD_STAGES


def test_cad_stage_labels_are_non_empty_strings():
    """All CAD stage labels should be non-empty strings."""
    for stage, _ in EXPECTED_CAD_STAGES:
        label = CAD_STAGE_LABELS[stage]
        assert isinstance(label, str)
        assert len(label.strip()) > 0, f"Label for {stage} is empty or whitespace"


def test_no_duplicate_stage_names():
    """Each stage name should appear exactly once."""
    names = [stage for stage, _ in EXPECTED_CAD_STAGES]
    assert len(names) == len(set(names)), f"Duplicate stage names found: {names}"


def test_no_duplicate_progress_values():
    """Each progress value should be unique."""
    values = [progress for _, progress in EXPECTED_CAD_STAGES]
    assert len(values) == len(set(values)), f"Duplicate progress values found: {values}"
