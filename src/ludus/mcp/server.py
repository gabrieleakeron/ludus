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

from ludus.mcp.client import LudusClient

mcp = FastMCP(
    "ludus",
    host=os.environ.get("LUDUS_MCP_HOST", "0.0.0.0"),
    port=int(os.environ.get("LUDUS_MCP_PORT", "8765")),
)


def _client() -> LudusClient:
    return LudusClient()


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
    """Create or update a scenario from a full YAML document.

    The YAML must contain at least `id`, `target` and `input.prompt_fixture`.
    """
    return _client().create_scenario(yaml_source)


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
