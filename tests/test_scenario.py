"""Tests for the scenario loader (AD3)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ludus.scenario import ScenarioError, load_scenario

SCENARIO_PATH = (
    Path(__file__).parent.parent / "scenarios" / "architect" / "breakdown-login.yaml"
)
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_scenario_happy_path() -> None:
    """Load the real scenario file without errors."""
    scenario = load_scenario(SCENARIO_PATH)
    assert scenario.id == "architetto-scomposizione-login"
    assert scenario.target == "mock.architect"
    assert scenario.repeat == 5
    assert len(scenario.expectations) == 3


def test_scenario_prompt_fixture_resolved_to_absolute() -> None:
    """prompt_fixture must be resolved to an absolute path."""
    scenario = load_scenario(SCENARIO_PATH)
    assert Path(scenario.input.prompt_fixture).is_absolute()
    assert Path(scenario.input.prompt_fixture).exists()


def test_scenario_rubric_path_resolved() -> None:
    """rubric path in llm_judge expectation must be absolute."""
    scenario = load_scenario(SCENARIO_PATH)
    llm_exp = next((e for e in scenario.expectations if e.type == "llm_judge"), None)
    assert llm_exp is not None
    assert llm_exp.rubric is not None
    assert Path(llm_exp.rubric).is_absolute()
    assert Path(llm_exp.rubric).exists()


def test_scenario_unknown_keys_ignored(tmp_path: Path) -> None:
    """gate, baseline, contract, code_gate must be silently ignored (forward-compat)."""
    scenario_data = {
        "id": "test-scenario",
        "target": "mock.architect",
        "repeat": 1,
        "input": {"prompt_fixture": str(FIXTURES_DIR / "stories" / "login.md")},
        "expectations": [{"type": "contains", "any_of": ["hello"]}],
        # Unknown M2+ keys — must not cause an error
        "gate": {"min_pass_rate": 0.9},
        "baseline": {"storage": "files"},
        "contract": {"schema": "v1"},
        "code_gate": {"lint": True},
        "some_future_key": {"nested": "value"},
    }
    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text(yaml.dump(scenario_data), encoding="utf-8")

    scenario = load_scenario(yaml_file)
    assert scenario.id == "test-scenario"


def test_scenario_missing_required_field_raises(tmp_path: Path) -> None:
    """Missing 'target' must raise ScenarioError."""
    scenario_data = {
        "id": "missing-target",
        # "target" is missing
        "input": {"prompt_fixture": "some/file.md"},
        "expectations": [],
    }
    yaml_file = tmp_path / "bad.yaml"
    yaml_file.write_text(yaml.dump(scenario_data), encoding="utf-8")

    with pytest.raises(ScenarioError):
        load_scenario(yaml_file)


def test_scenario_missing_input_raises(tmp_path: Path) -> None:
    """Missing 'input' must raise ScenarioError."""
    scenario_data = {
        "id": "missing-input",
        "target": "mock.architect",
        # input is missing
        "expectations": [],
    }
    yaml_file = tmp_path / "bad2.yaml"
    yaml_file.write_text(yaml.dump(scenario_data), encoding="utf-8")

    with pytest.raises(ScenarioError):
        load_scenario(yaml_file)


def test_scenario_file_not_found_raises() -> None:
    with pytest.raises(ScenarioError, match="not found"):
        load_scenario("/nonexistent/path/scenario.yaml")


def test_scenario_relative_paths_in_tmp(tmp_path: Path) -> None:
    """Relative prompt_fixture is resolved relative to scenario file, not cwd."""
    # Create a fixture file inside tmp
    story = tmp_path / "story.md"
    story.write_text("# Story", encoding="utf-8")

    scenario_data = {
        "id": "relative-test",
        "target": "mock.architect",
        "repeat": 1,
        "input": {"prompt_fixture": "story.md"},  # relative
        "expectations": [{"type": "contains", "any_of": ["Story"]}],
    }
    yaml_file = tmp_path / "scenario.yaml"
    yaml_file.write_text(yaml.dump(scenario_data), encoding="utf-8")

    scenario = load_scenario(yaml_file)
    resolved = Path(scenario.input.prompt_fixture)
    assert resolved.is_absolute()
    assert resolved == tmp_path / "story.md"
