"""SQLModel tables — the persistence mapping of the ludus domain.

These mirror the core Pydantic models (`ludus.models`, `ludus.scenario`,
`ludus.baseline`) but add DB identity/timestamps. Rich nested structures
(RunResult, Evaluation lists) are stored as JSON columns; flat numeric fields
are extracted for cheap querying / GUI display.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column, Text
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class TargetRow(SQLModel, table=True):
    """A registered target (seeded from ludus.adapters registry)."""

    __tablename__ = "targets"

    key: str = Field(primary_key=True)  # e.g. "mock.architect"
    kind: str = "adapter"
    description: str = ""
    requires_api_key: bool = False


class ScenarioRow(SQLModel, table=True):
    """A scenario known to the backend (seeded from disk or created via API)."""

    __tablename__ = "scenarios"

    id: str = Field(primary_key=True)  # scenario.id
    target: str
    description: str = ""
    repeat: int = 1
    source_path: str | None = None  # absolute path to the YAML on disk
    yaml_source: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class RunRow(SQLModel, table=True):
    """One batch execution of a scenario (N repetitions aggregated)."""

    __tablename__ = "runs"

    id: int | None = Field(default=None, primary_key=True)
    scenario_id: str = Field(index=True, foreign_key="scenarios.id")
    target: str
    n: int
    status: str = "completed"  # batch-level: completed | error
    overall_mean: float = 0.0
    pass_rate: float = 0.0
    gate_evaluated: bool = False
    gate_passed: bool | None = None
    report_text: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=_utcnow)


class RunOutcomeRow(SQLModel, table=True):
    """One repetition within a run — a serialized RunResult + its Evaluations."""

    __tablename__ = "run_outcomes"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(index=True, foreign_key="runs.id")
    idx: int  # 0-based repetition index
    status: str = "completed"
    score: float = 0.0  # mean of this run's evaluator scores
    # Extracted trace metrics for querying / display:
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    tokens_input: int = 0
    tokens_output: int = 0
    # Full fidelity, serialized via .model_dump():
    result_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    evaluations_json: list[Any] = Field(default_factory=list, sa_column=Column(JSON))


class BaselineRow(SQLModel, table=True):
    """Persisted baseline (mirror of ludus.baseline.Baseline)."""

    __tablename__ = "baselines"

    scenario_id: str = Field(primary_key=True)
    target: str | None = None
    overall_mean: float
    pass_rate: float
    n: int
    timestamp: str
    ludus_version: str
