"""Ludus MCP server (FastMCP, streamable HTTP transport).

Exposes the backend as MCP tools so a Claude plugin can create scenarios, load
targets, trigger runs and read results. Every tool is a thin proxy to the REST
API (see client.py); no evaluation logic lives here.

Environment:
  LUDUS_API_URL   backend base URL (default http://localhost:8000)
  LUDUS_MCP_HOST  bind host (default 0.0.0.0)
  LUDUS_MCP_PORT  bind port (default 8765)
"""

from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from ludus.mcp.client import LudusApiError, LudusClient

mcp = FastMCP(
    "ludus",
    host=os.environ.get("LUDUS_MCP_HOST", "0.0.0.0"),
    port=int(os.environ.get("LUDUS_MCP_PORT", "8765")),
)


def _client() -> LudusClient:
    return LudusClient()


def _call(fn, *args: Any, **kwargs: Any) -> Any:  # type: ignore[no-untyped-def]
    """Invoke a client write call, surfacing backend errors as a clean message.

    Converts LudusApiError into a plain RuntimeError so MCP tool callers
    never see a raw httpx stack trace. The message is passed through as-is:
    LudusApiError/_format_error already renders a self-describing "Ludus API
    error (<status>): <detail>" string, so no extra prefix is added here —
    a bare passthrough avoids mislabeling e.g. a 404/409 as "Validation
    failed", which previously happened regardless of the actual status.
    """
    try:
        return fn(*args, **kwargs)
    except LudusApiError as exc:
        raise RuntimeError(str(exc)) from exc


@mcp.tool()
def list_targets() -> Any:
    """List the evaluation targets (adapters) registered in Ludus."""
    return _client().list_targets()


@mcp.tool()
def list_scenarios() -> Any:
    """List all scenarios known to the Ludus backend."""
    return _client().list_scenarios()


@mcp.tool()
def get_scenario(scenario_id: str) -> Any:
    """Get a single scenario (metadata + YAML source) by id."""
    return _client().get_scenario(scenario_id)


@mcp.tool()
def create_scenario(yaml_source: str) -> Any:
    """Create a new scenario from a full YAML document.

    The YAML must be a mapping with a safe `id` (matching `[a-z0-9._-]+`);
    `target` and `input.prompt_fixture` are required as well but are
    validated separately when the scenario is loaded. Use update_scenario
    to modify a scenario that already exists.
    """
    return _call(_client().create_scenario, yaml_source)


@mcp.tool()
def update_scenario(scenario_id: str, yaml_source: str) -> Any:
    """Update an existing scenario's YAML in place.

    The YAML's `id` field must match `scenario_id`. Fails with a clear error
    (404 from the backend) if no scenario with this id exists yet — use
    create_scenario for that case instead.
    """
    return _call(_client().update_scenario, scenario_id, yaml_source)


@mcp.tool()
def register_target(key: str, description: str = "", requires_api_key: bool = True) -> Any:
    """Declare an authoring-only target so scenarios can reference it.

    This does NOT make the target runnable — it is only usable by scenarios
    until a matching core adapter is implemented and registered. Declaring a
    key that already names a runnable adapter fails (the adapter is the
    source of truth for runnable targets; reference it directly instead).
    """
    return _call(
        _client().register_target,
        key,
        description=description,
        requires_api_key=requires_api_key,
    )


@mcp.tool()
def run_scenario(
    scenario_id: str,
    target: str | None = None,
    n: int | None = None,
    update_baseline: bool = False,
) -> Any:
    """Run a scenario N times and return the persisted run with aggregates.

    Args:
        scenario_id: The scenario to execute.
        target: Optional target override (e.g. "mock.architect").
        n: Optional repetition-count override.
        update_baseline: If true, persist this run's aggregates as the baseline.
    """
    return _client().run_scenario(scenario_id, target=target, n=n, update_baseline=update_baseline)


@mcp.tool()
def list_runs(scenario_id: str | None = None) -> Any:
    """List runs, optionally filtered by scenario id."""
    return _client().list_runs(scenario_id)


@mcp.tool()
def get_run(run_id: int) -> Any:
    """Get a run's full detail, including per-repetition outcomes."""
    return _client().get_run(run_id)


@mcp.tool()
def get_baseline(scenario_id: str) -> Any:
    """Get the stored regression baseline for a scenario."""
    return _client().get_baseline(scenario_id)


def run() -> None:
    """Console-script / module entry point — serve over streamable HTTP."""
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    run()
