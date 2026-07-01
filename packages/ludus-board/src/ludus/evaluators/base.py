"""Evaluator abstract base class.

All evaluators implement evaluate(run_result) -> Evaluation.
They MUST read only run_result.artifact and run_result.trace;
run_result.raw is adapter-internal and is NEVER read by a judge.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ludus.models import Evaluation, RunResult


class Evaluator(ABC):
    """Base class for all evaluators (deterministic and LLM-as-judge)."""

    @abstractmethod
    def evaluate(self, run_result: RunResult) -> Evaluation:
        """Apply this evaluator to a RunResult and return an Evaluation.

        Implementations MUST only read run_result.artifact and run_result.trace.
        """
