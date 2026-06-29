"""CLI entry point for Ludus.

Usage:
    ludus run <scenario.yaml> [--repeat/-n N] [--target T]

Exits 0 on success, 1 on error.
"""
from __future__ import annotations

import sys

import click

from ludus.harness import Harness
from ludus.report import Reporter
from ludus.scenario import ScenarioError, load_scenario


@click.group()
def main() -> None:
    """Ludus AI — evaluation framework for AI systems."""


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
def run_cmd(scenario_path: str, repeat: int | None, target: str | None) -> None:
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

    reporter = Reporter()
    report = reporter.render(scenario=scenario, outcomes=outcomes)
    click.echo(report)
    sys.exit(0)
