"""Unit tests for the Ludus MCP server tool error wrapping.

Verifies register_target/update_scenario/create_scenario surface backend
errors as a clean RuntimeError (the LudusApiError message passed through
as-is) rather than propagating raw httpx exceptions or mislabeling
non-400 statuses as "Validation failed".
"""

from __future__ import annotations

import pytest

from ludus.mcp.client import LudusApiError
from ludus.mcp.server import _call


def test_call_wraps_ludus_api_error_as_runtime_error() -> None:
    def boom() -> None:
        raise LudusApiError("Ludus API error (404): Scenario 'x' not found.")

    with pytest.raises(RuntimeError) as exc_info:
        _call(boom)

    message = str(exc_info.value)
    assert message == "Ludus API error (404): Scenario 'x' not found."
    assert "Scenario 'x' not found." in message


def test_call_does_not_mislabel_non_400_as_validation_failed() -> None:
    def boom() -> None:
        raise LudusApiError("Ludus API error (409): Target 'x' already exists.")

    with pytest.raises(RuntimeError) as exc_info:
        _call(boom)

    assert "Validation failed" not in str(exc_info.value)


def test_call_passes_through_return_value() -> None:
    def ok(x: int, y: int = 1) -> int:
        return x + y

    assert _call(ok, 2, y=3) == 5
