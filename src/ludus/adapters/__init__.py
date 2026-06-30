"""Adapter registry.

resolve(target: str) -> Adapter  maps a target string to an Adapter instance.

Registered targets:
  "mock.architect"           -> MockAdapter (default M1 target, keyless)
  "sethlans.agent.architect" -> SingleSubagentAdapter (Level A, requires API key)
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ludus.adapters.base import Adapter
from ludus.adapters.mock import MockAdapter

# Lazy import for SingleSubagentAdapter (optional extra)
_GOLDEN_DEFAULT = (
    Path(__file__).parent.parent.parent.parent
    / "fixtures"
    / "golden"
    / "architect-breakdown-login.json"
)


def _make_mock(golden_path: Path | None = None) -> MockAdapter:
    gp = golden_path or _GOLDEN_DEFAULT
    return MockAdapter(golden_path=gp if gp.exists() else None)


def _make_single_subagent() -> Adapter:
    from ludus.adapters.single_subagent import SingleSubagentAdapter

    return SingleSubagentAdapter()


# Registry maps target string -> factory callable
_REGISTRY: dict[str, Callable[[], Adapter]] = {
    "mock.architect": _make_mock,
    "sethlans.agent.architect": _make_single_subagent,
}


def resolve(target: str) -> Adapter:
    """Return an Adapter instance for the given target string.

    Args:
        target: One of the registered target keys (e.g. "mock.architect").

    Raises:
        KeyError: If the target is not registered.
        RuntimeError: If the target requires capabilities not available (e.g. no API key).
    """
    if target not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY.keys()))
        raise KeyError(f"Unknown target '{target}'. Available: {available}")

    return _REGISTRY[target]()
