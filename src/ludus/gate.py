"""Gate evaluation for M2 (AD-M2-3, AD-M2-4).

Turns aggregated run outcomes into a machine-actionable PASS/FAIL verdict
by evaluating two sub-checks:

1. ``min_pass_rate`` — fraction of N runs where all evaluators passed
   must be >= ``gate.min_pass_rate``.
2. ``regression`` — current overall_mean must not drop more than
   ``gate.max_regression_vs_baseline`` below the stored baseline mean.
   Status is ``n/a`` when no baseline is present (neutral, never fails).

Sub-check combination (AD-M2-3):
    Overall verdict = PASS iff every *applicable* sub-check is PASS.
    ``n/a`` sub-checks are never counted as failures.

Functions
---------
compute_pass_rate(outcomes) -> float
evaluate_gate(scenario, outcomes, baseline) -> GateResult
"""

from __future__ import annotations

from pydantic import BaseModel

from ludus.aggregate import overall_mean as compute_overall_mean
from ludus.baseline import Baseline
from ludus.models import RunOutcome
from ludus.scenario import Scenario


class SubCheck(BaseModel):
    """Result of one gate sub-check."""

    name: str
    """Identifier: ``"min_pass_rate"`` or ``"regression"``."""

    status: str
    """``"PASS"`` | ``"FAIL"`` | ``"n/a"``."""

    value: float | None = None
    """Computed value (pass_rate or regression delta). None when ``status == "n/a"``."""

    threshold: float | None = None
    """The configured threshold from the gate block."""

    detail: str = ""
    """Human-readable explanation."""


class GateResult(BaseModel):
    """Outcome of evaluating a scenario's gate policy."""

    evaluated: bool
    """False when the scenario has no ``gate:`` block — no evaluation took place."""

    passed: bool
    """True when not evaluated, or when all applicable sub-checks are PASS."""

    sub_checks: list[SubCheck] = []
    """Ordered list of sub-checks; empty when ``evaluated is False``."""

    pass_rate: float | None = None
    """Computed pass_rate (fraction of passing runs). None when not evaluated."""

    overall_mean: float | None = None
    """Computed overall mean score for this run. None when not evaluated."""


def compute_pass_rate(outcomes: list[RunOutcome]) -> float:
    """Compute the fraction of runs where every evaluator passed (AD-M2-2).

    A run is a **pass** iff ``all(e.passed for e in outcome.evaluations)``.
    Runs with zero evaluations count as PASS (``all([]) == True``).

    Args:
        outcomes: List of RunOutcome from Harness.run().

    Returns:
        Float in [0.0 .. 1.0]; 0.0 when ``outcomes`` is empty.
    """
    n = len(outcomes)
    if n == 0:
        return 0.0
    passing = sum(1 for o in outcomes if all(e.passed for e in o.evaluations))
    return passing / n


def evaluate_gate(
    scenario: Scenario,
    outcomes: list[RunOutcome],
    baseline: Baseline | None,
) -> GateResult:
    """Evaluate the scenario gate policy and return a GateResult.

    Pure function — no I/O, no side-effects.

    Args:
        scenario: Parsed Scenario; ``scenario.gate`` may be None.
        outcomes: List of RunOutcome from Harness.run().
        baseline: Previously persisted Baseline, or None when absent.

    Returns:
        A ``GateResult``:
        - ``evaluated=False, passed=True`` when the scenario has no gate.
        - Otherwise evaluates ``min_pass_rate`` and optionally ``regression``.
    """
    if scenario.gate is None:
        return GateResult(evaluated=False, passed=True)

    gate = scenario.gate
    sub_checks: list[SubCheck] = []

    # --- Compute aggregates (shared helper — no duplication) ---
    pr = compute_pass_rate(outcomes)
    om = compute_overall_mean(outcomes)

    # --- Sub-check 1: min_pass_rate (always applicable) ---
    pr_pass = pr >= gate.min_pass_rate
    sub_checks.append(
        SubCheck(
            name="min_pass_rate",
            status="PASS" if pr_pass else "FAIL",
            value=round(pr, 6),
            threshold=gate.min_pass_rate,
            detail=f"pass_rate={pr:.4f} vs threshold={gate.min_pass_rate:.4f}",
        )
    )

    # --- Sub-check 2: regression (applicable only when baseline is present) ---
    if baseline is None:
        sub_checks.append(
            SubCheck(
                name="regression",
                status="n/a",
                value=None,
                threshold=gate.max_regression_vs_baseline,
                detail="no baseline — regression check skipped",
            )
        )
    else:
        regression_delta = baseline.overall_mean - om
        reg_pass = regression_delta <= gate.max_regression_vs_baseline
        sub_checks.append(
            SubCheck(
                name="regression",
                status="PASS" if reg_pass else "FAIL",
                value=round(regression_delta, 6),
                threshold=gate.max_regression_vs_baseline,
                detail=(
                    f"baseline_mean={baseline.overall_mean:.4f} "
                    f"current_mean={om:.4f} "
                    f"delta={regression_delta:.4f} "
                    f"tolerance={gate.max_regression_vs_baseline:.4f}"
                ),
            )
        )

    # Overall verdict: PASS iff all *applicable* (non-n/a) sub-checks are PASS
    applicable = [sc for sc in sub_checks if sc.status != "n/a"]
    gate_passed = all(sc.status == "PASS" for sc in applicable)

    return GateResult(
        evaluated=True,
        passed=gate_passed,
        sub_checks=sub_checks,
        pass_rate=round(pr, 6),
        overall_mean=round(om, 6),
    )
