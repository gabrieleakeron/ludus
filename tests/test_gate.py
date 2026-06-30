"""Unit tests for gate.py — gate logic, pass_rate, regression (AD-M2-2, AD-M2-3)."""

from __future__ import annotations

import pytest

from ludus.baseline import Baseline
from ludus.gate import GateResult, SubCheck, compute_pass_rate, evaluate_gate
from ludus.models import Artifact, Evaluation, RunOutcome, RunResult, Tokens, Trace
from ludus.scenario import Gate, Scenario, ScenarioInput

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_outcome(passed_flags: list[bool], score: float = 0.8) -> RunOutcome:
    """Build a RunOutcome with evaluations whose passed flags match the given list."""
    evals = [Evaluation(type="contains", score=score if p else 0.0, passed=p) for p in passed_flags]
    rr = RunResult(
        artifact=Artifact(type="text", text="ok"),
        trace=Trace(tokens=Tokens(), cost_usd=0.001, latency_ms=50.0),
    )
    return RunOutcome(run_result=rr, evaluations=evals)


def _make_scenario(
    min_pass_rate: float = 0.8,
    max_regression: float = 0.05,
    with_gate: bool = True,
) -> Scenario:
    """Build a minimal Scenario, optionally with a Gate."""
    gate = Gate(min_pass_rate=min_pass_rate, max_regression_vs_baseline=max_regression)
    return Scenario(
        id="test-scenario",
        target="mock.architect",
        repeat=1,
        input=ScenarioInput(prompt_fixture="/tmp/story.md"),
        gate=gate if with_gate else None,
    )


def _make_baseline(overall_mean: float = 0.9, pass_rate: float = 0.9) -> Baseline:
    return Baseline(
        scenario_id="test-scenario",
        overall_mean=overall_mean,
        pass_rate=pass_rate,
        n=5,
        timestamp="2026-01-01T00:00:00+00:00",
        ludus_version="0.1.0",
    )


# ---------------------------------------------------------------------------
# compute_pass_rate (AC3)
# ---------------------------------------------------------------------------


def test_compute_pass_rate_all_pass() -> None:
    """All runs all-evaluator-pass => pass_rate == 1.0 (AC3)."""
    outcomes = [_make_outcome([True, True]) for _ in range(5)]
    assert compute_pass_rate(outcomes) == pytest.approx(1.0)


def test_compute_pass_rate_mixed_results() -> None:
    """3 passing out of 5 => pass_rate == 0.6 (AC3)."""
    outcomes = [
        _make_outcome([True, True]),
        _make_outcome([True, True]),
        _make_outcome([True, True]),
        _make_outcome([True, False]),  # one evaluator fails => run FAILS
        _make_outcome([False, True]),  # one evaluator fails => run FAILS
    ]
    assert compute_pass_rate(outcomes) == pytest.approx(0.6)


def test_compute_pass_rate_all_fail() -> None:
    """All runs with at least one failing evaluator => pass_rate == 0.0."""
    outcomes = [_make_outcome([True, False]) for _ in range(4)]
    assert compute_pass_rate(outcomes) == pytest.approx(0.0)


def test_compute_pass_rate_empty_outcomes() -> None:
    """No outcomes => 0.0."""
    assert compute_pass_rate([]) == pytest.approx(0.0)


def test_compute_pass_rate_zero_evaluations_counts_as_pass() -> None:
    """A run with zero evaluations counts as PASS (all([]) == True, AD-M2-2)."""
    outcome = RunOutcome(
        run_result=RunResult(
            artifact=Artifact(type="text", text="ok"),
            trace=Trace(tokens=Tokens()),
        ),
        evaluations=[],
    )
    assert compute_pass_rate([outcome]) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# min_pass_rate sub-check (AC4)
# ---------------------------------------------------------------------------


def test_gate_min_pass_rate_pass_branch() -> None:
    """pass_rate >= threshold => min_pass_rate sub-check PASS (AC4)."""
    # 5 out of 5 pass => pass_rate = 1.0 >= 0.9
    outcomes = [_make_outcome([True]) for _ in range(5)]
    scenario = _make_scenario(min_pass_rate=0.9)
    result = evaluate_gate(scenario, outcomes, baseline=None)
    assert result.evaluated is True
    pr_check = next(sc for sc in result.sub_checks if sc.name == "min_pass_rate")
    assert pr_check.status == "PASS"


def test_gate_min_pass_rate_fail_branch() -> None:
    """pass_rate < threshold => min_pass_rate sub-check FAIL (AC4)."""
    # 3 out of 5 pass => pass_rate = 0.6 < 0.9
    outcomes = [
        _make_outcome([True]),
        _make_outcome([True]),
        _make_outcome([True]),
        _make_outcome([False]),
        _make_outcome([False]),
    ]
    scenario = _make_scenario(min_pass_rate=0.9)
    result = evaluate_gate(scenario, outcomes, baseline=None)
    assert result.evaluated is True
    pr_check = next(sc for sc in result.sub_checks if sc.name == "min_pass_rate")
    assert pr_check.status == "FAIL"
    assert result.passed is False


# ---------------------------------------------------------------------------
# regression sub-check (AC6, AC7)
# ---------------------------------------------------------------------------


def test_gate_regression_pass_within_tolerance() -> None:
    """Small drop within tolerance => regression PASS (AC6)."""
    # baseline mean = 0.9; current mean depends on outcomes
    # each outcome has one eval with score 0.88 => overall_mean = 0.88
    # regression = 0.9 - 0.88 = 0.02 <= max_regression 0.05 => PASS
    outcomes = [_make_outcome([True], score=0.88) for _ in range(5)]
    scenario = _make_scenario(min_pass_rate=0.0, max_regression=0.05)
    baseline = _make_baseline(overall_mean=0.9)
    result = evaluate_gate(scenario, outcomes, baseline=baseline)
    reg_check = next(sc for sc in result.sub_checks if sc.name == "regression")
    assert reg_check.status == "PASS"


def test_gate_regression_pass_improvement() -> None:
    """Improvement (negative delta) always passes (AC6)."""
    # baseline mean = 0.7; current mean = 0.9 => regression = -0.2 <= 0.05 => PASS
    outcomes = [_make_outcome([True], score=0.9) for _ in range(5)]
    scenario = _make_scenario(min_pass_rate=0.0, max_regression=0.05)
    baseline = _make_baseline(overall_mean=0.7)
    result = evaluate_gate(scenario, outcomes, baseline=baseline)
    reg_check = next(sc for sc in result.sub_checks if sc.name == "regression")
    assert reg_check.status == "PASS"


def test_gate_regression_fail_exceeds_tolerance() -> None:
    """Drop > tolerance => regression FAIL (AC6)."""
    # baseline mean = 0.9; current mean = 0.8 => regression = 0.1 > max_regression 0.05 => FAIL
    outcomes = [_make_outcome([True], score=0.8) for _ in range(5)]
    scenario = _make_scenario(min_pass_rate=0.0, max_regression=0.05)
    baseline = _make_baseline(overall_mean=0.9)
    result = evaluate_gate(scenario, outcomes, baseline=baseline)
    reg_check = next(sc for sc in result.sub_checks if sc.name == "regression")
    assert reg_check.status == "FAIL"
    assert result.passed is False


def test_gate_regression_na_when_no_baseline() -> None:
    """No baseline => regression sub-check n/a, gate does not fail (AC7)."""
    # pass_rate = 1.0 >= 0.9 => min_pass_rate PASS; regression n/a => overall PASS
    outcomes = [_make_outcome([True]) for _ in range(5)]
    scenario = _make_scenario(min_pass_rate=0.9, max_regression=0.05)
    result = evaluate_gate(scenario, outcomes, baseline=None)
    reg_check = next(sc for sc in result.sub_checks if sc.name == "regression")
    assert reg_check.status == "n/a"
    assert reg_check.value is None
    assert result.passed is True


# ---------------------------------------------------------------------------
# No-gate scenario
# ---------------------------------------------------------------------------


def test_gate_no_gate_evaluated_false() -> None:
    """Scenario without gate => evaluated=False, passed=True."""
    outcomes = [_make_outcome([False]) for _ in range(5)]  # would all fail
    scenario = _make_scenario(with_gate=False)
    result = evaluate_gate(scenario, outcomes, baseline=None)
    assert result.evaluated is False
    assert result.passed is True
    assert result.sub_checks == []


# ---------------------------------------------------------------------------
# GateResult models
# ---------------------------------------------------------------------------


def test_gate_result_structure() -> None:
    """GateResult and SubCheck expose the right fields."""
    sub = SubCheck(name="min_pass_rate", status="PASS", value=0.9, threshold=0.8, detail="ok")
    gr = GateResult(evaluated=True, passed=True, sub_checks=[sub], pass_rate=0.9, overall_mean=0.85)
    assert gr.evaluated is True
    assert gr.sub_checks[0].name == "min_pass_rate"
    assert gr.overall_mean == pytest.approx(0.85)
