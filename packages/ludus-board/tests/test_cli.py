"""End-to-end CLI test — verifies `ludus run` prints score+cost and exits 0.

M2 additions: gate pass/fail exit codes and GATE section rendering (AC8, AC9).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from ludus.cli import main

SCENARIO_PATH = str(
    Path(__file__).parent.parent / "scenarios" / "architect" / "breakdown-login.yaml"
)


def test_cli_run_mock_scenario_exits_0() -> None:
    """ludus run <scenario.yaml> must exit 0 on the mock path (gate bypassed for M1 compat)."""
    runner = CliRunner()
    result = runner.invoke(main, ["run", SCENARIO_PATH, "--repeat", "2", "--no-gate"])
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
        main, ["run", SCENARIO_PATH, "--repeat", "1", "--target", "mock.architect", "--no-gate"]
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


# ---------------------------------------------------------------------------
# M2 gate + baseline CLI tests
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _write_scenario(tmp_path: Path, gate_block: dict | None = None) -> str:
    """Write a minimal scenario YAML to tmp_path and return its path string."""
    data: dict = {
        "id": "cli-test-scenario",
        "target": "mock.architect",
        "repeat": 2,
        "input": {"prompt_fixture": str(FIXTURES_DIR / "stories" / "login.md")},
        "expectations": [{"type": "contains", "any_of": ["FastAPI"]}],
    }
    if gate_block is not None:
        data["gate"] = gate_block
    p = tmp_path / "scenario.yaml"
    p.write_text(yaml.dump(data), encoding="utf-8")
    return str(p)


def test_cli_gate_pass_exits_0(tmp_path: Path) -> None:
    """Gate with min_pass_rate=0.0 always passes => GATE section + exit 0 (AC9)."""
    scenario_path = _write_scenario(
        tmp_path, gate_block={"min_pass_rate": 0.0, "max_regression_vs_baseline": 0.5}
    )
    runner = CliRunner()
    result = runner.invoke(main, ["run", scenario_path])
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}:\n{result.output}"
    assert "GATE" in result.output
    assert "Overall verdict: PASS" in result.output


def test_cli_gate_fail_exits_1(tmp_path: Path) -> None:
    """Gate with min_pass_rate=2.0 (impossible) => GATE section + exit 1 (AC8)."""
    scenario_path = _write_scenario(
        tmp_path,
        gate_block={"min_pass_rate": 2.0, "max_regression_vs_baseline": 0.05},
    )
    runner = CliRunner()
    result = runner.invoke(main, ["run", scenario_path])
    assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}:\n{result.output}"
    assert "GATE" in result.output
    assert "Overall verdict: FAIL" in result.output


def test_cli_no_gate_exits_0(tmp_path: Path) -> None:
    """Scenario without gate: block still exits 0 (AC2 — M1 backward-compat)."""
    scenario_path = _write_scenario(tmp_path, gate_block=None)
    runner = CliRunner()
    result = runner.invoke(main, ["run", scenario_path])
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}:\n{result.output}"
    # GATE section must NOT appear in M1 backward-compat mode
    assert "GATE" not in result.output


def test_cli_no_gate_flag_forces_exit_0(tmp_path: Path) -> None:
    """--no-gate skips evaluation even when gate is defined => always exit 0."""
    scenario_path = _write_scenario(
        tmp_path,
        gate_block={"min_pass_rate": 2.0, "max_regression_vs_baseline": 0.05},
    )
    runner = CliRunner()
    result = runner.invoke(main, ["run", scenario_path, "--no-gate"])
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}:\n{result.output}"


def test_cli_gate_section_in_addition_to_m1_report(tmp_path: Path) -> None:
    """GATE section is rendered IN ADDITION to SCORE SUMMARY / COST (AC10)."""
    scenario_path = _write_scenario(
        tmp_path, gate_block={"min_pass_rate": 0.0, "max_regression_vs_baseline": 0.5}
    )
    runner = CliRunner()
    result = runner.invoke(main, ["run", scenario_path])
    assert "Overall mean score" in result.output
    assert "Total cost" in result.output
    assert "GATE" in result.output


def test_cli_update_baseline_writes_file(tmp_path: Path) -> None:
    """--update-baseline creates a baseline JSON file."""
    scenario_path = _write_scenario(
        tmp_path, gate_block={"min_pass_rate": 0.0, "max_regression_vs_baseline": 0.5}
    )

    runner = CliRunner()
    # Patch DEFAULT_BASELINES_DIR via env is not straightforward; instead invoke with
    # a workaround: change cwd so DEFAULT_BASELINES_DIR resolves under tmp_path.
    import os

    old_cwd = os.getcwd()
    try:
        os.chdir(str(tmp_path))
        result = runner.invoke(main, ["run", scenario_path, "--update-baseline"])
    finally:
        os.chdir(old_cwd)

    assert result.exit_code == 0, f"Expected exit 0:\n{result.output}"
    # The baseline file should exist under cwd/baselines/
    bl_file = tmp_path / "baselines" / "cli-test-scenario.json"
    assert bl_file.exists(), f"Baseline file not found at {bl_file}"


def test_cli_baseline_update_subcommand(tmp_path: Path) -> None:
    """ludus baseline update SCENARIO writes a baseline and exits 0."""
    scenario_path = _write_scenario(tmp_path)  # no gate needed for baseline update
    import os

    old_cwd = os.getcwd()
    try:
        os.chdir(str(tmp_path))
        runner = CliRunner()
        result = runner.invoke(main, ["baseline", "update", scenario_path])
    finally:
        os.chdir(old_cwd)

    assert result.exit_code == 0, f"Expected exit 0:\n{result.output}"
    bl_file = tmp_path / "baselines" / "cli-test-scenario.json"
    assert bl_file.exists(), f"Baseline file not found at {bl_file}"
