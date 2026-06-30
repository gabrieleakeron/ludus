"""Tests for RunResult / Artifact / Trace Pydantic models (AD4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ludus.models import (
    Artifact,
    Evaluation,
    RunOutcome,
    RunResult,
    Trace,
)

GOLDEN_PATH = (
    Path(__file__).parent.parent / "fixtures" / "golden" / "architect-breakdown-login.json"
)


def test_run_result_validates_on_golden_fixture() -> None:
    """RunResult must validate on the recorded golden fixture (AC2)."""
    raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    result = RunResult.model_validate(raw)
    assert result.status == "completed"
    assert result.artifact.type == "breakdown"
    assert result.artifact.text is not None
    assert result.artifact.structured_json is not None


def test_trace_carries_required_fields() -> None:
    """Trace must carry tool_calls, tokens, cost, latency, session_id (AC3)."""
    raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    result = RunResult.model_validate(raw)
    trace = result.trace
    assert len(trace.tool_calls) > 0
    assert trace.tokens.input > 0
    assert trace.tokens.output > 0
    assert trace.cost_usd > 0.0
    assert trace.latency_ms > 0.0
    assert trace.session_id is not None


def test_tool_call_fields() -> None:
    raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    result = RunResult.model_validate(raw)
    first_tc = result.trace.tool_calls[0]
    assert first_tc.name == "Read"
    assert "file_path" in first_tc.input


def test_artifact_files() -> None:
    raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    result = RunResult.model_validate(raw)
    assert len(result.artifact.files) == 1
    assert result.artifact.files[0].path == "tasks.md"


def test_run_result_raw_is_dict() -> None:
    """raw field exists and is a dict (adapter-internal, never read by evaluators)."""
    raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    result = RunResult.model_validate(raw)
    assert isinstance(result.raw, dict)
    assert result.raw.get("source") == "golden-fixture"


def test_evaluation_model() -> None:
    ev = Evaluation(type="schema", score=0.9, passed=True, detail="ok")
    assert ev.type == "schema"
    assert ev.score == pytest.approx(0.9)


def test_run_outcome_model() -> None:
    rr = RunResult(
        artifact=Artifact(type="text", text="hello"),
        trace=Trace(),
    )
    ev = Evaluation(type="contains", score=1.0, passed=True)
    outcome = RunOutcome(run_result=rr, evaluations=[ev])
    assert len(outcome.evaluations) == 1
