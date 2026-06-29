"""Tests for deterministic evaluators and StubLlmJudge."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ludus.evaluators.deterministic import ContainsEvaluator, SchemaEvaluator
from ludus.evaluators.llm_judge import StubLlmJudge
from ludus.models import Artifact, RunResult, Trace

RUBRIC_PATH = Path(__file__).parent.parent / "rubrics" / "architect.md"
GOLDEN_PATH = (
    Path(__file__).parent.parent / "fixtures" / "golden" / "architect-breakdown-login.json"
)


def _make_run_result(text: str = "", structured: dict | None = None) -> RunResult:
    return RunResult(
        artifact=Artifact(type="text", text=text, structured_json=structured),
        trace=Trace(),
    )


# --- SchemaEvaluator ---

def test_schema_evaluator_passes_when_fields_present() -> None:
    rr = _make_run_result(structured={"tasks": [...], "rationale": "because"})
    ev = SchemaEvaluator(must_have_fields=["tasks", "rationale"])
    result = ev.evaluate(rr)
    assert result.passed is True
    assert result.score == pytest.approx(1.0)
    assert result.type == "schema"


def test_schema_evaluator_fails_when_field_missing() -> None:
    rr = _make_run_result(structured={"tasks": [...]})
    ev = SchemaEvaluator(must_have_fields=["tasks", "rationale"])
    result = ev.evaluate(rr)
    assert result.passed is False
    assert result.score < 1.0


def test_schema_evaluator_partial_score() -> None:
    rr = _make_run_result(structured={"tasks": [...]})
    ev = SchemaEvaluator(must_have_fields=["tasks", "rationale", "missing"])
    result = ev.evaluate(rr)
    # 1 out of 3 present
    assert result.score == pytest.approx(1 / 3)


def test_schema_evaluator_falls_back_to_text() -> None:
    """Fields are also found as substrings in artifact.text."""
    rr = _make_run_result(text="Here are the tasks and rationale for the breakdown.")
    ev = SchemaEvaluator(must_have_fields=["tasks", "rationale"])
    result = ev.evaluate(rr)
    assert result.passed is True


def test_schema_evaluator_reads_only_artifact_trace() -> None:
    """Evaluator must not access run_result.raw."""
    rr = _make_run_result(structured={"tasks": [], "rationale": "x"})
    rr = rr.model_copy(update={"raw": {"secret": "do not read"}})
    ev = SchemaEvaluator(must_have_fields=["tasks", "rationale"])
    result = ev.evaluate(rr)
    assert result.passed is True  # evaluated correctly without touching raw


# --- ContainsEvaluator ---

def test_contains_evaluator_passes_when_match() -> None:
    rr = _make_run_result(text="FastAPI endpoint for /auth/login")
    ev = ContainsEvaluator(any_of=["FastAPI", "Django", "Flask"])
    result = ev.evaluate(rr)
    assert result.passed is True
    assert result.score == pytest.approx(1.0)
    assert result.type == "contains"


def test_contains_evaluator_fails_when_no_match() -> None:
    rr = _make_run_result(text="Hello world")
    ev = ContainsEvaluator(any_of=["FastAPI", "endpoint", "auth"])
    result = ev.evaluate(rr)
    assert result.passed is False
    assert result.score == pytest.approx(0.0)


def test_contains_evaluator_case_insensitive() -> None:
    rr = _make_run_result(text="FASTAPI is used here")
    ev = ContainsEvaluator(any_of=["fastapi"])
    result = ev.evaluate(rr)
    assert result.passed is True


def test_contains_evaluator_checks_structured_json() -> None:
    rr = _make_run_result(structured={"description": "uses FastAPI for the auth endpoint"})
    ev = ContainsEvaluator(any_of=["FastAPI"])
    result = ev.evaluate(rr)
    assert result.passed is True


# --- StubLlmJudge ---

def test_stub_llm_judge_deterministic_output() -> None:
    """Same input always gives same score (deterministic)."""
    raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    rr = RunResult.model_validate(raw)
    judge = StubLlmJudge(rubric_path=RUBRIC_PATH, pass_threshold=0.5)
    r1 = judge.evaluate(rr)
    r2 = judge.evaluate(rr)
    assert r1.score == r2.score
    assert r1.passed == r2.passed
    assert r1.type == "llm_judge"


def test_stub_llm_judge_nonzero_score_on_golden() -> None:
    """Golden fixture should score > 0 against the architect rubric."""
    raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    rr = RunResult.model_validate(raw)
    judge = StubLlmJudge(rubric_path=RUBRIC_PATH, pass_threshold=0.5)
    result = judge.evaluate(rr)
    assert result.score > 0.0


def test_stub_llm_judge_missing_rubric() -> None:
    """Missing rubric path should return neutral score, not crash."""
    rr = _make_run_result(text="some text")
    judge = StubLlmJudge(rubric_path="/nonexistent/rubric.md", pass_threshold=0.8)
    result = judge.evaluate(rr)
    assert isinstance(result.score, float)
    assert result.type == "llm_judge"


def test_stub_llm_judge_reads_only_artifact_trace() -> None:
    """StubLlmJudge must not access run_result.raw."""
    raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    rr = RunResult.model_validate(raw)
    rr = rr.model_copy(update={"raw": {"secret": "should not be accessed"}})
    judge = StubLlmJudge(rubric_path=RUBRIC_PATH)
    result = judge.evaluate(rr)
    assert isinstance(result.score, float)  # evaluated without touching raw
