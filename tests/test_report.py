"""Tests for Reporter — mean/variance math and output format."""

from __future__ import annotations

from pathlib import Path

import pytest

from ludus.models import Artifact, Evaluation, RunOutcome, RunResult, Tokens, Trace
from ludus.report import Reporter, _population_variance
from ludus.scenario import load_scenario

SCENARIO_PATH = Path(__file__).parent.parent / "scenarios" / "architect" / "breakdown-login.yaml"


def _make_outcome(scores: list[float], cost: float = 0.001, latency: float = 100.0) -> RunOutcome:
    evals = [Evaluation(type=f"type_{i}", score=s, passed=s >= 0.5) for i, s in enumerate(scores)]
    rr = RunResult(
        artifact=Artifact(type="text", text="hello"),
        trace=Trace(
            tokens=Tokens(input=100, output=50),
            cost_usd=cost,
            latency_ms=latency,
        ),
    )
    return RunOutcome(run_result=rr, evaluations=evals)


# --- Math helpers ---


def test_population_variance_identical_values() -> None:
    """Variance of identical values is 0."""
    assert _population_variance([1.0, 1.0, 1.0, 1.0]) == pytest.approx(0.0)


def test_population_variance_known_values() -> None:
    """Population variance of [1, 2, 3] = 2/3."""
    result = _population_variance([1.0, 2.0, 3.0])
    assert result == pytest.approx(2 / 3)


def test_population_variance_empty() -> None:
    assert _population_variance([]) == 0.0


# --- Reporter stats ---


def test_reporter_variance_zero_on_identical_mock_runs() -> None:
    """Mock path: all runs identical → variance == 0 (AC5 + AD6/O4)."""
    scenario = load_scenario(SCENARIO_PATH)
    # Simulate 5 identical outcomes (same scores)
    outcomes = [_make_outcome([1.0, 1.0, 0.8]) for _ in range(5)]

    reporter = Reporter()
    report = reporter.render(scenario=scenario, outcomes=outcomes)

    # Variance should be 0 (all per-run aggregate scores are identical: (1+1+0.8)/3 = 0.933...)
    assert "Population variance : 0.000000" in report


def test_reporter_nonzero_variance_on_differing_runs() -> None:
    """Non-identical runs must produce non-zero variance."""
    scenario = load_scenario(SCENARIO_PATH)
    outcomes = [
        _make_outcome([1.0]),
        _make_outcome([0.5]),
        _make_outcome([0.0]),
    ]
    reporter = Reporter()
    report = reporter.render(scenario=scenario, outcomes=outcomes)
    # Per-run scores: [1.0, 0.5, 0.0] — variance = ((1-0.5)^2 + 0 + (0-0.5)^2)/3 = 0.1667
    assert "Population variance : 0.166667" in report


def test_reporter_correct_mean_on_known_values() -> None:
    """Mean of [1.0, 0.5, 0.0] should be 0.5."""
    scenario = load_scenario(SCENARIO_PATH)
    outcomes = [_make_outcome([1.0]), _make_outcome([0.5]), _make_outcome([0.0])]
    reporter = Reporter()
    report = reporter.render(scenario=scenario, outcomes=outcomes)
    assert "Overall mean score  : 0.5000" in report


def test_reporter_output_contains_score_and_cost() -> None:
    """Console report must contain score and cost (CLI acceptance)."""
    scenario = load_scenario(SCENARIO_PATH)
    outcomes = [_make_outcome([0.9, 0.8], cost=0.005) for _ in range(2)]
    reporter = Reporter()
    report = reporter.render(scenario=scenario, outcomes=outcomes)
    assert "Overall mean score" in report
    assert "Total cost" in report
    assert "$" in report


def test_reporter_stddev_matches_variance() -> None:
    scenario = load_scenario(SCENARIO_PATH)
    outcomes = [_make_outcome([1.0]), _make_outcome([0.0])]
    reporter = Reporter()
    report = reporter.render(scenario=scenario, outcomes=outcomes)
    # variance = 0.25; stddev = 0.5
    assert "Population variance : 0.250000" in report
    assert "Std deviation       : 0.500000" in report


def test_reporter_per_evaluator_section() -> None:
    scenario = load_scenario(SCENARIO_PATH)
    outcomes = [
        _make_outcome([1.0, 0.8]),
        _make_outcome([0.5, 0.6]),
    ]
    reporter = Reporter()
    report = reporter.render(scenario=scenario, outcomes=outcomes)
    assert "PER-EVALUATOR MEANS" in report


def test_reporter_empty_outcomes() -> None:
    scenario = load_scenario(SCENARIO_PATH)
    reporter = Reporter()
    report = reporter.render(scenario=scenario, outcomes=[])
    assert "No outcomes" in report
