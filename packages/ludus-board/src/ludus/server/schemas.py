"""API request/response DTOs (kept separate from the DB table models)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TargetOut(BaseModel):
    key: str
    kind: str = "adapter"
    description: str = ""
    requires_api_key: bool = False
    runnable: bool = Field(
        default=False,
        description="Computed at read time: True iff key is in ludus.adapters._REGISTRY.",
    )


class TargetCreate(BaseModel):
    """Declare an authoring-only target (kind='declared')."""

    key: str = Field(..., description="Target key, charset [a-z0-9._-]+.")
    description: str = ""
    requires_api_key: bool = True


class ScenarioOut(BaseModel):
    id: str
    target: str
    description: str = ""
    repeat: int = 1
    source_path: str | None = None
    yaml_source: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ScenarioCreate(BaseModel):
    """Create/update a scenario from raw YAML text."""

    yaml_source: str = Field(..., description="Full scenario YAML document.")


class RunCreate(BaseModel):
    """Trigger a run of a stored scenario."""

    scenario_id: str
    target: str | None = Field(None, description="Override the scenario target.")
    n: int | None = Field(None, description="Override the repetition count.")
    update_baseline: bool = False


class RunOutcomeOut(BaseModel):
    idx: int
    status: str
    score: float
    cost_usd: float
    latency_ms: float
    tokens_input: int
    tokens_output: int
    result_json: dict[str, Any]
    evaluations_json: list[Any]


class RunSummaryOut(BaseModel):
    id: int
    scenario_id: str
    target: str
    n: int
    status: str
    overall_mean: float
    pass_rate: float
    gate_evaluated: bool
    gate_passed: bool | None = None
    created_at: datetime | None = None


class RunDetailOut(RunSummaryOut):
    report_text: str | None = None
    outcomes: list[RunOutcomeOut] = Field(default_factory=list)


class BaselineOut(BaseModel):
    scenario_id: str
    target: str | None = None
    overall_mean: float
    pass_rate: float
    n: int
    timestamp: str
    ludus_version: str


# --------------------------------------------------------------------------
# Fixtures (story s6886e332 / task tcbec12d4) — see the story's `## API
# Contract` section for the authoritative shapes; these mirror it 1:1.
# --------------------------------------------------------------------------


class FixtureRefOut(BaseModel):
    root: str  # "fixtures" | "rubrics"
    path: str  # relative to root, forward-slash
    role: str  # "prompt_fixture" | "context_files" | "rubric"
    scenario_id: str
    present: bool
    size_bytes: int | None = None
    is_binary: bool | None = None
    content_type: str | None = None


class FixtureUsedByOut(BaseModel):
    scenario_id: str
    role: str


class FixtureContentOut(BaseModel):
    root: str
    path: str
    present: bool
    size_bytes: int | None = None
    is_binary: bool = False
    truncated: bool = False
    content: str | None = None
    content_type: str | None = None
    used_by: list[FixtureUsedByOut] = Field(default_factory=list)


class FixtureUploadOut(BaseModel):
    root: str
    path: str
    size_bytes: int
    created: bool


class FixtureConfigOut(BaseModel):
    roots: list[str]
    preview_max_bytes: int
    upload_max_bytes: int
    text_extensions: list[str]
    upload_extensions: list[str]
