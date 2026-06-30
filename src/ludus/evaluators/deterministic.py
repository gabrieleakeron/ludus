"""Deterministic evaluators.

SchemaEvaluator  — checks that all must_have_fields appear in the artifact's
                   structured_json or (as substrings) in artifact.text.
ContainsEvaluator — checks that at least one of the any_of strings appears
                    in artifact.text or artifact.structured_json (serialized).
"""

from __future__ import annotations

import json

from ludus.evaluators.base import Evaluator
from ludus.models import Evaluation, RunResult


def _artifact_text(run_result: RunResult) -> str:
    """Flatten artifact to searchable text."""
    artifact = run_result.artifact
    parts: list[str] = []
    if artifact.text:
        parts.append(artifact.text)
    if artifact.structured_json:
        parts.append(json.dumps(artifact.structured_json))
    for f in artifact.files:
        if f.content:
            parts.append(f.content)
    return "\n".join(parts)


class SchemaEvaluator(Evaluator):
    """Checks that all required fields appear in the artifact.

    For structured_json: checks dict keys recursively (top-level only in M1).
    For text-only artifacts: checks substrings.
    """

    def __init__(self, must_have_fields: list[str]) -> None:
        self._fields = must_have_fields

    def evaluate(self, run_result: RunResult) -> Evaluation:
        artifact = run_result.artifact
        missing: list[str] = []

        for field in self._fields:
            found = False
            if artifact.structured_json and field in artifact.structured_json:
                found = True
            elif artifact.text and field in artifact.text:
                found = True
            if not found:
                missing.append(field)

        passed = len(missing) == 0
        score = 1.0 if passed else max(0.0, (len(self._fields) - len(missing)) / len(self._fields))
        detail = "All required fields present." if passed else f"Missing fields: {missing}"

        return Evaluation(type="schema", score=score, passed=passed, detail=detail)


class ContainsEvaluator(Evaluator):
    """Checks that at least one of the any_of strings appears in the artifact."""

    def __init__(self, any_of: list[str]) -> None:
        self._any_of = any_of

    def evaluate(self, run_result: RunResult) -> Evaluation:
        text = _artifact_text(run_result).lower()
        matched = [s for s in self._any_of if s.lower() in text]

        passed = len(matched) > 0
        score = 1.0 if passed else 0.0
        detail = f"Found: {matched}" if passed else f"None of {self._any_of} found in artifact."

        return Evaluation(type="contains", score=score, passed=passed, detail=detail)
