"""Core data models for Ludus.

These Pydantic models are the load-bearing contract (AD4):
  RunResult / Artifact / Trace / ToolCall / Tokens / ArtifactFile
  Evaluation / RunOutcome

Evaluators read ONLY `artifact` and `trace`; adapter internals live in `raw`.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ArtifactFile(BaseModel):
    """A file produced as part of an artifact."""

    path: str
    content: str | None = None
    ref: str | None = None  # URL or ref when content is external


class Artifact(BaseModel):
    """The output produced by a Target run."""

    type: str  # "breakdown" | "text" | "code" | ...
    text: str | None = None
    structured_json: dict[str, Any] | None = None
    files: list[ArtifactFile] = Field(default_factory=list)


class ToolCall(BaseModel):
    """One tool invocation captured in a trace."""

    name: str
    input: dict[str, Any] = Field(default_factory=dict)
    output: str | None = None
    parent_tool_use_id: str | None = None
    phase: str | None = None  # optional phase label (e.g. "pre", "post")


class Tokens(BaseModel):
    """Token usage for a run."""

    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0


class Trace(BaseModel):
    """Execution trace captured from the adapter."""

    tool_calls: list[ToolCall] = Field(default_factory=list)
    tokens: Tokens = Field(default_factory=Tokens)
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    session_id: str | None = None
    messages: list[dict[str, Any]] = Field(default_factory=list)


class RunResult(BaseModel):
    """Envelope returned by every Adapter.run() call."""

    artifact: Artifact
    trace: Trace
    status: Literal["completed", "budget_exceeded", "timeout", "error"] = "completed"
    raw: dict[str, Any] = Field(default_factory=dict)  # adapter-specific; NEVER read by evaluators


class Evaluation(BaseModel):
    """Result of one Evaluator applied to a RunResult."""

    type: str  # "schema" | "contains" | "llm_judge"
    score: float  # [0.0 .. 1.0]
    passed: bool
    detail: str = ""


class RunOutcome(BaseModel):
    """One repetition: a RunResult plus its evaluations."""

    run_result: RunResult
    evaluations: list[Evaluation] = Field(default_factory=list)
