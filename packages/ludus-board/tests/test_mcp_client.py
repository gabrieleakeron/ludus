"""Unit tests for the Ludus MCP client's error surfacing and new write methods.

Uses httpx.MockTransport (stdlib to httpx, no extra test dependency) to fake
backend responses without a live server.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from ludus.mcp.client import LudusApiError, LudusClient


def _client_with_transport(handler) -> LudusClient:  # type: ignore[no-untyped-def]
    """Build a LudusClient whose internal httpx.Client uses a mock transport."""
    client = LudusClient(base_url="http://testserver")

    def _request(method: str, path: str, **kwargs: Any) -> Any:
        url = f"{client._base}{path}"
        with httpx.Client(transport=httpx.MockTransport(handler), timeout=5) as http_client:
            resp = http_client.request(method, url, **kwargs)
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                from ludus.mcp.client import _format_error

                raise LudusApiError(_format_error(exc)) from exc
            if resp.content:
                return resp.json()
            return None

    client._request = _request  # type: ignore[method-assign]
    return client


def test_register_target_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/targets"
        assert request.method == "POST"
        return httpx.Response(201, json={"key": "custom.tool", "kind": "declared"})

    client = _client_with_transport(handler)
    result = client.register_target("custom.tool")
    assert result["key"] == "custom.tool"


def test_update_scenario_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/scenarios/my-id"
        assert request.method == "PUT"
        return httpx.Response(200, json={"id": "my-id"})

    client = _client_with_transport(handler)
    result = client.update_scenario("my-id", "id: my-id\ntarget: mock.architect\n")
    assert result["id"] == "my-id"


def test_update_scenario_404_raises_clean_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Scenario 'missing' not found."})

    client = _client_with_transport(handler)
    with pytest.raises(LudusApiError) as exc_info:
        client.update_scenario("missing", "id: missing\n")

    message = str(exc_info.value)
    assert "404" in message
    assert "Scenario 'missing' not found." in message
    # No raw traceback content leaking into the message itself.
    assert "Traceback" not in message


def test_register_target_409_raises_clean_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409, json={"detail": "Target 'mock.architect' already exists as a runnable adapter."}
        )

    client = _client_with_transport(handler)
    with pytest.raises(LudusApiError) as exc_info:
        client.register_target("mock.architect")

    assert "already exists as a runnable adapter" in str(exc_info.value)


def test_format_error_falls_back_to_text_when_no_json_detail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    client = _client_with_transport(handler)
    with pytest.raises(LudusApiError) as exc_info:
        client.register_target("x")

    assert "500" in str(exc_info.value)
