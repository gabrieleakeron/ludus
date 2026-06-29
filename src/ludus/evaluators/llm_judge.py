"""LLM-as-judge evaluators.

StubLlmJudge     — keyword-heuristic, no API, deterministic. Default when no API key.
AnthropicLlmJudge — calls the Anthropic Messages API with a rubric. Activated when
                    ANTHROPIC_API_KEY is present.

Both implement the same Evaluator interface and read ONLY artifact+trace.
"""
from __future__ import annotations

import os
from pathlib import Path

from ludus.evaluators.base import Evaluator
from ludus.models import Evaluation, RunResult


class StubLlmJudge(Evaluator):
    """Rubric-keyword heuristic judge — no API, fully deterministic.

    Reads the rubric file and checks how many of its headings / bullet keywords
    appear in the artifact.  Score = fraction_matched (0..1).
    Passes if score >= pass_threshold.
    """

    def __init__(self, rubric_path: str | Path, pass_threshold: float = 0.8) -> None:
        self._rubric_path = Path(rubric_path)
        self._pass_threshold = pass_threshold
        self._keywords = self._extract_keywords()

    def _extract_keywords(self) -> list[str]:
        """Extract short, matchable keywords from the rubric .md file.

        Strategy: from each non-empty line, extract individual words >= 5 chars.
        This produces tokens that can realistically appear in an artifact.
        """
        if not self._rubric_path.exists():
            return []
        import re

        text = self._rubric_path.read_text(encoding="utf-8")
        # Extract all words of length >= 5 from the rubric
        words = re.findall(r"\b[a-zA-Z]{5,}\b", text)
        # Lowercase and deduplicate
        seen: set[str] = set()
        unique: list[str] = []
        for w in words:
            lw = w.lower()
            if lw not in seen:
                seen.add(lw)
                unique.append(lw)
        return unique[:30]  # cap at 30 keywords

    def evaluate(self, run_result: RunResult) -> Evaluation:
        import json

        artifact = run_result.artifact
        text_parts: list[str] = []
        if artifact.text:
            text_parts.append(artifact.text.lower())
        if artifact.structured_json:
            text_parts.append(json.dumps(artifact.structured_json).lower())

        combined = " ".join(text_parts)

        if not self._keywords:
            # No rubric keywords — give a neutral score
            score = 0.75
            passed = score >= self._pass_threshold
            return Evaluation(
                type="llm_judge",
                score=score,
                passed=passed,
                detail="StubLlmJudge: no rubric keywords found; neutral score applied.",
            )

        matched = [kw for kw in self._keywords if kw in combined]
        score = len(matched) / len(self._keywords)
        passed = score >= self._pass_threshold
        detail = (
            f"StubLlmJudge: {len(matched)}/{len(self._keywords)} rubric keywords matched "
            f"(threshold={self._pass_threshold:.0%}). Matched: {matched[:5]}"
        )

        return Evaluation(type="llm_judge", score=round(score, 4), passed=passed, detail=detail)


class AnthropicLlmJudge(Evaluator):
    """Calls Anthropic Messages API to score the artifact against a rubric.

    Only instantiated when ANTHROPIC_API_KEY is set and anthropic is installed.
    """

    def __init__(
        self,
        rubric_path: str | Path,
        pass_threshold: float = 0.8,
        model: str = "claude-haiku-4-5",
    ) -> None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "AnthropicLlmJudge requires ANTHROPIC_API_KEY. "
                "Use StubLlmJudge for keyless evaluation."
            )
        try:
            import anthropic as _  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "anthropic is not installed. Install the [llm] optional extra."
            ) from exc

        self._rubric_path = Path(rubric_path)
        self._pass_threshold = pass_threshold
        self._model = model

    def evaluate(self, run_result: RunResult) -> Evaluation:
        import json

        import anthropic

        artifact = run_result.artifact
        artifact_text = artifact.text or json.dumps(artifact.structured_json or {})
        rubric_text = (
            self._rubric_path.read_text(encoding="utf-8")
            if self._rubric_path.exists()
            else "Evaluate the quality of the following output."
        )

        prompt = (
            f"You are an evaluator. Score the following AI-generated output against the rubric.\n\n"
            f"## Rubric\n{rubric_text}\n\n"
            f"## Output to evaluate\n{artifact_text}\n\n"
            f"Respond with a JSON object: {{\"score\": <0.0-1.0>, \"reasoning\": \"<brief>\"}}. "
            f"Score 1.0 = fully meets rubric, 0.0 = does not meet it at all."
        )

        client = anthropic.Anthropic()
        try:
            response = client.messages.create(
                model=self._model,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text if response.content else "{}"
            # Parse JSON from response
            import re

            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                score = float(parsed.get("score", 0.0))
                reasoning = str(parsed.get("reasoning", ""))
            else:
                score = 0.5
                reasoning = f"Could not parse JSON from response: {content[:100]}"
        except Exception as exc:
            return Evaluation(
                type="llm_judge",
                score=0.0,
                passed=False,
                detail=f"AnthropicLlmJudge error: {exc}",
            )

        passed = score >= self._pass_threshold
        return Evaluation(
            type="llm_judge",
            score=round(score, 4),
            passed=passed,
            detail=f"AnthropicLlmJudge (model={self._model}): {reasoning}",
        )


def make_llm_judge(rubric_path: str | Path, pass_threshold: float = 0.8) -> Evaluator:
    """Factory: return AnthropicLlmJudge when key is present, else StubLlmJudge."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return AnthropicLlmJudge(rubric_path=rubric_path, pass_threshold=pass_threshold)
        except (ImportError, RuntimeError):
            pass
    return StubLlmJudge(rubric_path=rubric_path, pass_threshold=pass_threshold)
