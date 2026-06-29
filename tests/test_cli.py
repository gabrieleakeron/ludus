"""End-to-end CLI test — verifies `ludus run` prints score+cost and exits 0."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from ludus.cli import main

SCENARIO_PATH = str(
    Path(__file__).parent.parent / "scenarios" / "architect" / "breakdown-login.yaml"
)


def test_cli_run_mock_scenario_exits_0() -> None:
    """ludus run <scenario.yaml> must exit 0 on the mock path."""
    runner = CliRunner()
    result = runner.invoke(main, ["run", SCENARIO_PATH, "--repeat", "2"])
    assert result.exit_code == 0, f"CLI exited with {result.exit_code}:\n{result.output}"


def test_cli_run_prints_score() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["run", SCENARIO_PATH, "--repeat", "2"])
    assert "Overall mean score" in result.output


def test_cli_run_prints_cost() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["run", SCENARIO_PATH, "--repeat", "2"])
    assert "Total cost" in result.output


def test_cli_run_with_target_override() -> None:
    """--target flag must override scenario target."""
    runner = CliRunner()
    result = runner.invoke(
        main, ["run", SCENARIO_PATH, "--repeat", "1", "--target", "mock.architect"]
    )
    assert result.exit_code == 0, result.output


def test_cli_run_unknown_target_exits_1() -> None:
    runner = CliRunner()
    result = runner.invoke(
        main, ["run", SCENARIO_PATH, "--repeat", "1", "--target", "nonexistent.adapter"]
    )
    assert result.exit_code == 1


def test_cli_run_missing_scenario_exits_1() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["run", "/nonexistent/scenario.yaml"])
    assert result.exit_code == 1


def test_cli_run_scenario_repeat_n() -> None:
    """n runs should produce N run detail lines in output."""
    runner = CliRunner()
    result = runner.invoke(main, ["run", SCENARIO_PATH, "--repeat", "3"])
    # Should see "Run  1", "Run  2", "Run  3"
    assert "Run  1" in result.output
    assert "Run  3" in result.output


@pytest.mark.live
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — Level A live test skipped",
)
def test_cli_run_level_a_live() -> None:
    """Live Level A test — only runs when ANTHROPIC_API_KEY is present."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "run",
            SCENARIO_PATH,
            "--repeat",
            "1",
            "--target",
            "sethlans.agent.architect",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Overall mean score" in result.output
