"""Harness — thin run-loop.

Harness.run(target, scenario, n) -> list[RunOutcome]

No aggregation, no printing.  Aggregation lives in the Reporter (AD5).
"""

from __future__ import annotations

from ludus.adapters import resolve
from ludus.evaluators import build_evaluators
from ludus.models import RunOutcome
from ludus.scenario import Scenario


class Harness:
    """Runs a Target against a Scenario N times and returns the raw outcomes."""

    def run(self, target: str, scenario: Scenario, n: int) -> list[RunOutcome]:
        """Execute target x scenario, n repetitions.

        Args:
            target: Target string (overrides scenario.target when provided).
            scenario: Parsed Scenario with input/context/expectations.
            n: Number of repetitions.

        Returns:
            List of RunOutcome (length == n), one per repetition.
        """
        adapter = resolve(target)
        evaluators = build_evaluators(scenario.expectations)
        outcomes: list[RunOutcome] = []

        for _ in range(n):
            run_result = adapter.run(
                scenario_input=scenario.input,
                context=scenario.context,
                run_config=scenario.run_config,
            )
            evaluations = [ev.evaluate(run_result) for ev in evaluators]
            outcomes.append(RunOutcome(run_result=run_result, evaluations=evaluations))

        return outcomes
