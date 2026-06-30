"""CLI entry point for Ludus.

Usage:
    ludus run <scenario.yaml> [--repeat/-n N] [--target T]
              [--update-baseline] [--no-gate]
    ludus baseline update <scenario.yaml> [--repeat/-n N] [--target T]

Exit codes:
    0  — success, or gate evaluated and PASSED, or no gate defined.
    1  — error loading scenario / runtime error, OR gate evaluated and FAILED.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from ludus.aggregate import overall_mean as compute_overall_mean
from ludus.baseline import DEFAULT_BASELINES_DIR, build_baseline, load_baseline, save_baseline
from ludus.gate import GateResult, compute_pass_rate, evaluate_gate
from ludus.harness import Harness
from ludus.report import Reporter, render_gate
from ludus.scenario import ScenarioError, load_scenario


@click.group()
def main() -> None:
    """Ludus AI — evaluation framework for AI systems."""


# ---------------------------------------------------------------------------
# ludus run
# ---------------------------------------------------------------------------


@main.command("run")
@click.argument("scenario_path", metavar="SCENARIO")
@click.option(
    "--repeat",
    "-n",
    default=None,
    type=int,
    help="Number of repetitions (overrides scenario 'repeat' field).",
)
@click.option(
    "--target",
    "-t",
    default=None,
    help="Override the scenario target (e.g. 'mock.architect').",
)
@click.option(
    "--update-baseline",
    is_flag=True,
    default=False,
    help="Persist this run's aggregated scores as the new baseline (after evaluating the gate).",
)
@click.option(
    "--no-gate",
    is_flag=True,
    default=False,
    help="Skip gate evaluation; always exit 0 (M1 backward-compat escape hatch).",
)
def run_cmd(
    scenario_path: str,
    repeat: int | None,
    target: str | None,
    update_baseline: bool,
    no_gate: bool,
) -> None:
    """Run SCENARIO end-to-end and print a score + cost report."""
    try:
        scenario = load_scenario(scenario_path)
    except ScenarioError as exc:
        click.echo(f"[ludus] Error loading scenario: {exc}", err=True)
        sys.exit(1)

    n = repeat if repeat is not None else scenario.repeat
    resolved_target = target if target is not None else scenario.target

    click.echo(
        f"[ludus] Running scenario '{scenario.id}'  target='{resolved_target}'  n={n} ...",
        err=True,
    )

    harness = Harness()
    try:
        outcomes = harness.run(target=resolved_target, scenario=scenario, n=n)
    except KeyError as exc:
        click.echo(f"[ludus] Unknown target: {exc}", err=True)
        sys.exit(1)
    except RuntimeError as exc:
        click.echo(f"[ludus] Runtime error: {exc}", err=True)
        sys.exit(1)
    except Exception as exc:
        click.echo(f"[ludus] Unexpected error: {exc}", err=True)
        sys.exit(1)

    # --- M1 report ---
    reporter = Reporter()
    report = reporter.render(scenario=scenario, outcomes=outcomes)
    click.echo(report)

    # --- M2 gate + baseline (AD-M2-4) ---
    baselines_dir = Path(DEFAULT_BASELINES_DIR).resolve()

    # Load baseline BEFORE optionally overwriting, so the regression check
    # compares against the OLD baseline (not the run just completed).
    existing_baseline = load_baseline(scenario.id, baselines_dir) if not no_gate else None

    if no_gate:
        gate_result: GateResult = GateResult(evaluated=False, passed=True)
    else:
        gate_result = evaluate_gate(scenario, outcomes, existing_baseline)

    if update_baseline:
        om = compute_overall_mean(outcomes)
        pr = compute_pass_rate(outcomes)
        bl = build_baseline(
            scenario_id=scenario.id,
            target=resolved_target,
            overall_mean=om,
            pass_rate=pr,
            n=n,
        )
        written = save_baseline(bl, baselines_dir)
        click.echo(f"[ludus] Baseline updated: {written}", err=True)

    gate_section = render_gate(gate_result)
    if gate_section:
        click.echo(gate_section)

    # Exit 1 iff gate was evaluated AND failed (AD-M2-4).
    if gate_result.evaluated and not gate_result.passed:
        sys.exit(1)

    sys.exit(0)


# ---------------------------------------------------------------------------
# ludus baseline update
# ---------------------------------------------------------------------------


@main.group("baseline")
def baseline_group() -> None:
    """Manage baselines for regression tracking."""


@baseline_group.command("update")
@click.argument("scenario_path", metavar="SCENARIO")
@click.option(
    "--repeat",
    "-n",
    default=None,
    type=int,
    help="Number of repetitions (overrides scenario 'repeat' field).",
)
@click.option(
    "--target",
    "-t",
    default=None,
    help="Override the scenario target.",
)
def baseline_update_cmd(
    scenario_path: str,
    repeat: int | None,
    target: str | None,
) -> None:
    """Run SCENARIO and write its aggregate scores as the new baseline.

    The gate is NOT enforced — this command always exits 0 on a successful run.
    Use this to explicitly set the baseline before enforcing the gate.
    """
    try:
        scenario = load_scenario(scenario_path)
    except ScenarioError as exc:
        click.echo(f"[ludus] Error loading scenario: {exc}", err=True)
        sys.exit(1)

    n = repeat if repeat is not None else scenario.repeat
    resolved_target = target if target is not None else scenario.target

    click.echo(
        f"[ludus] (baseline update) Running scenario '{scenario.id}'  "
        f"target='{resolved_target}'  n={n} ...",
        err=True,
    )

    harness = Harness()
    try:
        outcomes = harness.run(target=resolved_target, scenario=scenario, n=n)
    except KeyError as exc:
        click.echo(f"[ludus] Unknown target: {exc}", err=True)
        sys.exit(1)
    except RuntimeError as exc:
        click.echo(f"[ludus] Runtime error: {exc}", err=True)
        sys.exit(1)
    except Exception as exc:
        click.echo(f"[ludus] Unexpected error: {exc}", err=True)
        sys.exit(1)

    om = compute_overall_mean(outcomes)
    pr = compute_pass_rate(outcomes)
    bl = build_baseline(
        scenario_id=scenario.id,
        target=resolved_target,
        overall_mean=om,
        pass_rate=pr,
        n=n,
    )
    baselines_dir = Path(DEFAULT_BASELINES_DIR).resolve()
    written = save_baseline(bl, baselines_dir)
    click.echo(f"[ludus] Baseline written: {written}", err=True)
    sys.exit(0)
