"""Shared aggregation helpers (AD-M2-4).

Extracted so both Reporter.render and gate.evaluate_gate use identical math
and do not duplicate the per-run-mean / overall-mean logic.

Functions
---------
per_run_scores(outcomes) -> list[float]
    Mean of each run's evaluator scores (0.0 when run has no evaluators).

overall_mean(outcomes) -> float
    Mean of per_run_scores; 0.0 when outcomes is empty.
"""

from __future__ import annotations

from ludus.models import RunOutcome


def per_run_scores(outcomes: list[RunOutcome]) -> list[float]:
    """Return the per-run aggregate score (mean of evaluator scores) for each outcome.

    A run with zero evaluators gets score 0.0.

    Args:
        outcomes: List of RunOutcome from Harness.run().

    Returns:
        List of floats, same length as ``outcomes``.
    """
    scores: list[float] = []
    for outcome in outcomes:
        evals = outcome.evaluations
        if evals:
            scores.append(sum(e.score for e in evals) / len(evals))
        else:
            scores.append(0.0)
    return scores


def overall_mean(outcomes: list[RunOutcome]) -> float:
    """Return the mean of per_run_scores; 0.0 when outcomes is empty.

    Args:
        outcomes: List of RunOutcome from Harness.run().

    Returns:
        Overall mean score in [0.0 .. 1.0].
    """
    if not outcomes:
        return 0.0
    scores = per_run_scores(outcomes)
    return sum(scores) / len(scores)
