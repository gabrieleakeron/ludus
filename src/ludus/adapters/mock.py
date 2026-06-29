"""MockAdapter — deterministic replay of a recorded golden RunResult.

Target key: "mock.architect"

Reads the golden fixture JSON next to the scenario (resolved via scenario_dir
or from a well-known default path).  Fully reproducible: no network, no API key.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from ludus.adapters.base import Adapter
from ludus.models import Artifact, RunResult, Trace
from ludus.scenario import Context, RunConfig, ScenarioInput


class MockAdapter(Adapter):
    """Replays a recorded golden RunResult from a fixture JSON file.

    Args:
        golden_path: Absolute path to the golden fixture JSON.
                     If None, the adapter constructs a minimal synthetic RunResult.
    """

    def __init__(self, golden_path: str | Path | None = None) -> None:
        self._golden_path = Path(golden_path) if golden_path else None

    def run(
        self,
        scenario_input: ScenarioInput,
        context: Context,
        run_config: RunConfig,
    ) -> RunResult:
        """Return the recorded golden RunResult (or a minimal synthetic one)."""
        if self._golden_path and self._golden_path.exists():
            try:
                raw = json.loads(self._golden_path.read_text(encoding="utf-8"))
                return RunResult.model_validate(raw)
            except (json.JSONDecodeError, ValidationError) as exc:
                # Degrade gracefully — return an error result rather than crashing
                return RunResult(
                    artifact=Artifact(type="error", text=f"Golden fixture parse error: {exc}"),
                    trace=Trace(),
                    status="error",
                    raw={"error": str(exc)},
                )

        # Synthetic fallback (no golden file configured)
        return _synthetic_run_result()


def _synthetic_run_result() -> RunResult:
    """Return a minimal but fully-populated synthetic RunResult for testing."""
    from ludus.models import ArtifactFile

    return RunResult(
        artifact=Artifact(
            type="breakdown",
            text=(
                "## Task Breakdown\n\n"
                "### Backend\n- FastAPI endpoint for /auth/login\n- JWT token generation\n"
                "### Frontend\n- Login form component\n- Auth service\n"
            ),
            structured_json={
                "tasks": [
                    {"id": 1, "title": "FastAPI auth endpoint", "rationale": "core requirement"},
                    {"id": 2, "title": "Login form", "rationale": "user facing"},
                ],
                "rationale": "Decomposed login story into backend auth and frontend form.",
            },
            files=[
                ArtifactFile(
                    path="tasks.md",
                    content="# Tasks\n1. FastAPI endpoint\n2. Login form",
                )
            ],
        ),
        trace=_synthetic_trace(),
        status="completed",
        raw={"source": "synthetic"},
    )


def _synthetic_trace():  # type: ignore[no-untyped-def]
    from ludus.models import Tokens, ToolCall, Trace

    return Trace(
        tool_calls=[
            ToolCall(
                name="Read",
                input={"file_path": "fixtures/stories/login.md"},
                output="# Login story\nAs a user I want to log in...",
                phase="analysis",
            ),
            ToolCall(
                name="Write",
                input={"file_path": "tasks.md", "content": "..."},
                output="File written",
                phase="output",
            ),
        ],
        tokens=Tokens(input=1200, output=480, cache_read=200, cache_write=50),
        cost_usd=0.0042,
        latency_ms=3150.0,
        session_id="mock-session-abc123",
        messages=[
            {"role": "user", "content": "Please break down the login story..."},
            {"role": "assistant", "content": "## Task Breakdown\n..."},
        ],
    )
