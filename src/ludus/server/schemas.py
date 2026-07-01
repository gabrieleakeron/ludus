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
