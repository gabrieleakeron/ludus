"""Adapter abstract base class.

Every Target sits behind an Adapter that knows how to invoke it.
The contract:
  - run() always returns a valid RunResult
  - failures map to status != "completed", never an unhandled exception
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ludus.models import RunResult
from ludus.scenario import Context, RunConfig, ScenarioInput


class Adapter(ABC):
    """Protocol all adapters must implement."""

    @abstractmethod
    def run(
        self,
        scenario_input: ScenarioInput,
        context: Context,
        run_config: RunConfig,
    ) -> RunResult:
        """Execute the Target once and return the RunResult.

        Must never raise — wrap failures in RunResult(status="error").
        """
