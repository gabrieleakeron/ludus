"""Tests for Harness — verifies it loops N times and returns N outcomes."""
from __future__ import annotations

from pathlib import Path

import pytest

from ludus.harness import Harness
from ludus.scenario import load_scenario

SCENARIO_PATH = (
    Path(__file__).parent.parent / "scenarios" / "architect" / "breakdown-login.yaml"
)


def test_harness_returns_n_outcomes() -> None:
    """Harness.run must return exactly N RunOutcome objects."""
    scenario = load_scenario(SCENARIO_PATH)
    harness = Harness()
    outcomes = harness.run(target="mock.architect", scenario=scenario, n=3)
    assert len(outcomes) == 3


def test_harness_each_outcome_has_evaluations() -> None:
    """Each outcome must carry evaluations (one per expectation)."""
    scenario = load_scenario(SCENARIO_PATH)
    harness = Harness()
    outcomes = harness.run(target="mock.architect", scenario=scenario, n=2)
    for outcome in outcomes:
        assert len(outcome.evaluations) == len(scenario.expectations)


def test_harness_mock_outcomes_identical() -> None:
    """MockAdapter is deterministic: all N outcomes must have the same status."""
    scenario = load_scenario(SCENARIO_PATH)
    harness = Harness()
    outcomes = harness.run(target="mock.architect", scenario=scenario, n=5)
    statuses = {o.run_result.status for o in outcomes}
    assert statuses == {"completed"}


def test_harness_respects_override_n() -> None:
    """n parameter overrides scenario.repeat."""
    scenario = load_scenario(SCENARIO_PATH)
    harness = Harness()
    outcomes = harness.run(target="mock.architect", scenario=scenario, n=1)
    assert len(outcomes) == 1


def test_harness_unknown_target_raises() -> None:
    scenario = load_scenario(SCENARIO_PATH)
    harness = Harness()
    with pytest.raises(KeyError, match="Unknown target"):
        harness.run(target="nonexistent.target", scenario=scenario, n=1)
