"""Evaluator factory.

build_evaluators(expectations) -> list[Evaluator]
"""

from __future__ import annotations

from ludus.evaluators.base import Evaluator
from ludus.evaluators.deterministic import ContainsEvaluator, SchemaEvaluator
from ludus.evaluators.llm_judge import StubLlmJudge as StubLlmJudge
from ludus.evaluators.llm_judge import make_llm_judge
from ludus.scenario import ExpectationSchema


def build_evaluators(expectations: list[ExpectationSchema]) -> list[Evaluator]:
    """Build an Evaluator list from the parsed scenario expectations.

    Args:
        expectations: List of ExpectationSchema from the Scenario.

    Returns:
        Ordered list of Evaluator instances.

    Raises:
        ValueError: If an unknown expectation type is encountered.
    """
    evaluators: list[Evaluator] = []

    for exp in expectations:
        if exp.type == "schema":
            evaluators.append(SchemaEvaluator(must_have_fields=exp.must_have_fields))
        elif exp.type == "contains":
            evaluators.append(ContainsEvaluator(any_of=exp.any_of))
        elif exp.type == "llm_judge":
            rubric = exp.rubric or ""
            evaluators.append(make_llm_judge(rubric_path=rubric, pass_threshold=exp.pass_threshold))
        else:
            raise ValueError(f"Unknown expectation type: '{exp.type}'")

    return evaluators
