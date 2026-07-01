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


class LudusApiError(RuntimeError):
    """Raised when the backend returns an error response.

    Carries a clean, human-readable message (including the backend's JSON
    `detail` when present) so MCP tool callers never see a raw stack trace.
    """


class LudusClient:
    """Synchronous client for the backend endpoints used by the MCP tools."""

    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self._base = (base_url or _base_url()).rstrip("/")
        self._timeout = timeout or DEFAULT_TIMEOUT

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self._base}{path}"
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.request(method, url, **kwargs)
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise LudusApiError(_format_error(exc)) from exc
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

    def update_scenario(self, scenario_id: str, yaml_source: str) -> Any:
        return self._request("PUT", f"/scenarios/{scenario_id}", json={"yaml_source": yaml_source})

    def register_target(
        self,
        key: str,
        description: str = "",
        requires_api_key: bool = True,
    ) -> Any:
        return self._request(
            "POST",
            "/targets",
            json={
                "key": key,
                "description": description,
                "requires_api_key": requires_api_key,
            },
        )

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


def _format_error(exc: httpx.HTTPStatusError) -> str:
    """Build a clean 'Ludus API error (<status>): <detail>' message from a failed response."""
    status = exc.response.status_code
    detail: str | None = None
    try:
        body = exc.response.json()
        if isinstance(body, dict):
            detail = body.get("detail")
    except ValueError:
        detail = None
    if detail is None:
        detail = exc.response.text or exc.response.reason_phrase
    return f"Ludus API error ({status}): {detail}"
