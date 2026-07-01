"""Tiny httpx wrapper around the Ludus backend REST API.

The base URL is read from LUDUS_API_URL (default http://localhost:8000).
"""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_TIMEOUT = float(os.environ.get("LUDUS_API_TIMEOUT", "120"))


def _base_url() -> str:
    return os.environ.get("LUDUS_API_URL", "http://localhost:8000").rstrip("/")


class LudusClient:
    """Synchronous client for the backend endpoints used by the MCP tools."""

    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self._base = (base_url or _base_url()).rstrip("/")
        self._timeout = timeout or DEFAULT_TIMEOUT

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self._base}{path}"
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.request(method, url, **kwargs)
            resp.raise_for_status()
            if resp.content:
                return resp.json()
            return None

    # --- reads ---
    def health(self) -> Any:
        return self._request("GET", "/health")

    def list_targets(self) -> Any:
        return self._request("GET", "/targets")

    def list_scenarios(self) -> Any:
        return self._request("GET", "/scenarios")

    def get_scenario(self, scenario_id: str) -> Any:
        return self._request("GET", f"/scenarios/{scenario_id}")

    def list_runs(self, scenario_id: str | None = None) -> Any:
        params = {"scenario_id": scenario_id} if scenario_id else None
        return self._request("GET", "/runs", params=params)

    def get_run(self, run_id: int) -> Any:
        return self._request("GET", f"/runs/{run_id}")

    def get_baseline(self, scenario_id: str) -> Any:
        return self._request("GET", f"/baselines/{scenario_id}")

    # --- writes ---
    def create_scenario(self, yaml_source: str) -> Any:
        return self._request("POST", "/scenarios", json={"yaml_source": yaml_source})

    def run_scenario(
        self,
        scenario_id: str,
        target: str | None = None,
        n: int | None = None,
        update_baseline: bool = False,
    ) -> Any:
        payload: dict[str, Any] = {
            "scenario_id": scenario_id,
            "update_baseline": update_baseline,
        }
        if target is not None:
            payload["target"] = target
        if n is not None:
            payload["n"] = n
        return self._request("POST", "/runs", json=payload)
