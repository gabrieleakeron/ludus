"""Scenario YAML loader (AD3).

Parses only the M1 subset:
  id, target, description, repeat, input.prompt_fixture,
  context.files, run_config{max_budget_usd, model, bare}, expectations[]

Unknown keys (gate, baseline, contract, code_gate) are silently ignored.
Paths in prompt_fixture / rubric / context.files are resolved relative
to the scenario file's parent directory.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class ScenarioError(Exception):
    """Raised when a scenario file cannot be parsed or is invalid."""


class ExpectationSchema(BaseModel):
    """One expectation entry (deterministic or llm_judge)."""

    type: str  # "schema" | "contains" | "llm_judge"
    must_have_fields: list[str] = Field(default_factory=list)
    any_of: list[str] = Field(default_factory=list)
    rubric: str | None = None  # relative path to rubric .md; resolved later
    pass_threshold: float = 0.8

    model_config = {"extra": "allow"}  # forward-compat: ignore unknown expectation keys


class ScenarioInput(BaseModel):
    """Driving input definition."""

    prompt_fixture: str  # relative path; resolved to absolute by load_scenario

    model_config = {"extra": "allow"}


class Context(BaseModel):
    """Upstream context files."""

    files: list[str] = Field(default_factory=list)  # relative paths; resolved to absolute

    model_config = {"extra": "allow"}


class RunConfig(BaseModel):
    """Per-run adapter knobs."""

    max_budget_usd: float = 0.50
    model: str | None = None
    bare: bool = True

    model_config = {"extra": "allow"}


class Scenario(BaseModel):
    """Parsed scenario — only M1 fields are exposed; unknown keys are dropped."""

    id: str
    target: str
    description: str = ""
    repeat: int = 1
    input: ScenarioInput
    context: Context = Field(default_factory=Context)
    run_config: RunConfig = Field(default_factory=RunConfig)
    expectations: list[ExpectationSchema] = Field(default_factory=list)

    # Set by load_scenario — not in YAML
    scenario_dir: Path = Field(default=Path("."), exclude=True)

    model_config = {"extra": "ignore"}  # ignore gate, baseline, contract, code_gate

    @field_validator("expectations", mode="before")
    @classmethod
    def _require_expectations(cls, v: Any) -> Any:
        if v is None:
            return []
        return v

    @model_validator(mode="after")
    def _resolve_paths(self) -> Scenario:
        """Resolve fixture + rubric + context paths relative to scenario_dir."""
        base = self.scenario_dir
        if not Path(self.input.prompt_fixture).is_absolute():
            self.input.prompt_fixture = str(base / self.input.prompt_fixture)
        resolved_files = []
        for f in self.context.files:
            resolved_files.append(str(base / f) if not Path(f).is_absolute() else f)
        self.context.files = resolved_files
        for exp in self.expectations:
            if exp.rubric and not Path(exp.rubric).is_absolute():
                exp.rubric = str(base / exp.rubric)
        return self


def load_scenario(path: str | Path) -> Scenario:
    """Parse a scenario YAML file and return a validated Scenario.

    Args:
        path: Absolute or relative path to the .yaml file.

    Returns:
        A fully resolved Scenario instance.

    Raises:
        ScenarioError: If the file is missing, unparseable, or lacks required fields.
    """
    p = Path(path).resolve()
    if not p.exists():
        raise ScenarioError(f"Scenario file not found: {p}")

    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ScenarioError(f"YAML parse error in {p}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ScenarioError(f"Scenario file must be a YAML mapping, got {type(raw).__name__}: {p}")

    # Inject the directory so the model validator can resolve relative paths
    raw["scenario_dir"] = str(p.parent)

    # Surfacing missing-required-field errors as ScenarioError
    from pydantic import ValidationError

    try:
        scenario = Scenario.model_validate(raw)
    except ValidationError as exc:
        raise ScenarioError(f"Scenario validation failed in {p}:\n{exc}") from exc

    return scenario
