"""Reporter — aggregates N RunOutcomes and renders a console report.

Aggregation (AD5):
  - per-run aggregate score = mean of that run's evaluator scores
  - overall mean + population variance + stddev of the per-run aggregate score
  - cost/tokens/latency totals & means
  - tool-call count
"""
from __future__ import annotations

import math
from collections import defaultdict

from ludus.models import RunOutcome
from ludus.scenario import Scenario


def _population_variance(values: list[float]) -> float:
    """Population variance (sigma^2, divisor N)."""
    n = len(values)
    if n == 0:
        return 0.0
    mean = sum(values) / n
    return sum((v - mean) ** 2 for v in values) / n


class Reporter:
    """Renders a console report from scenario + N outcomes."""

    def render(self, scenario: Scenario, outcomes: list[RunOutcome]) -> str:
        """Compute statistics and return a formatted console string.

        Args:
            scenario: The parsed Scenario (for metadata).
            outcomes: List of RunOutcome from Harness.run().

        Returns:
            A multi-line formatted string ready for print().
        """
        n = len(outcomes)
        if n == 0:
            return "No outcomes to report."

        # --- Per-run aggregate score ---
        per_run_scores: list[float] = []
        for outcome in outcomes:
            evals = outcome.evaluations
            if evals:
                per_run_scores.append(sum(e.score for e in evals) / len(evals))
            else:
                per_run_scores.append(0.0)

        overall_mean = sum(per_run_scores) / n
        variance = _population_variance(per_run_scores)
        stddev = math.sqrt(variance)

        # --- Per-evaluator means ---
        eval_scores_by_type: dict[str, list[float]] = defaultdict(list)
        eval_pass_by_type: dict[str, list[bool]] = defaultdict(list)
        for outcome in outcomes:
            for ev in outcome.evaluations:
                eval_scores_by_type[ev.type].append(ev.score)
                eval_pass_by_type[ev.type].append(ev.passed)

        # --- Cost/tokens/latency/tool-calls ---
        total_cost = sum(o.run_result.trace.cost_usd for o in outcomes)
        total_input_tokens = sum(o.run_result.trace.tokens.input for o in outcomes)
        total_output_tokens = sum(o.run_result.trace.tokens.output for o in outcomes)
        total_latency = sum(o.run_result.trace.latency_ms for o in outcomes)
        total_tool_calls = sum(len(o.run_result.trace.tool_calls) for o in outcomes)

        mean_cost = total_cost / n
        mean_latency = total_latency / n

        # --- Format ---
        sep = "=" * 60
        thin = "-" * 60

        lines: list[str] = [
            "",
            sep,
            f"  LUDUS REPORT — {scenario.id}",
            sep,
            f"  Target   : {scenario.target}",
            f"  Runs (N) : {n}",
            thin,
            "  SCORE SUMMARY",
            thin,
            f"  Overall mean score  : {overall_mean:.4f}",
            f"  Population variance : {variance:.6f}",
            f"  Std deviation       : {stddev:.6f}",
            thin,
            "  PER-EVALUATOR MEANS",
            thin,
        ]

        for eval_type, scores in sorted(eval_scores_by_type.items()):
            mean_score = sum(scores) / len(scores)
            pass_rate = sum(1 for p in eval_pass_by_type[eval_type] if p) / len(
                eval_pass_by_type[eval_type]
            )
            lines.append(
                f"  [{eval_type:<14}]  mean={mean_score:.4f}  pass_rate={pass_rate:.0%}"
            )

        lines += [
            thin,
            "  COST / TOKENS / LATENCY",
            thin,
            f"  Total cost (USD)   : ${total_cost:.6f}  (mean/run ${mean_cost:.6f})",
            f"  Input tokens       : {total_input_tokens:,}",
            f"  Output tokens      : {total_output_tokens:,}",
            f"  Total latency (ms) : {total_latency:,.0f}  (mean/run {mean_latency:,.0f} ms)",
            f"  Tool calls         : {total_tool_calls}  (mean/run {total_tool_calls / n:.1f})",
            thin,
            "  PER-RUN DETAIL",
            thin,
        ]

        for i, (outcome, score) in enumerate(zip(outcomes, per_run_scores, strict=True), 1):
            status = outcome.run_result.status
            cost = outcome.run_result.trace.cost_usd
            lat = outcome.run_result.trace.latency_ms
            tc = len(outcome.run_result.trace.tool_calls)
            eval_summary = "  ".join(
                f"{e.type}={e.score:.2f}({'PASS' if e.passed else 'FAIL'})"
                for e in outcome.evaluations
            )
            lines.append(
                f"  Run {i:>2}  score={score:.4f}  status={status}  "
                f"cost=${cost:.6f}  lat={lat:.0f}ms  tools={tc}"
            )
            if eval_summary:
                lines.append(f"         {eval_summary}")

        lines += [sep, ""]
        return "\n".join(lines)
