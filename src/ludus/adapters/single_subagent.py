"""SingleSubagentAdapter — Level A adapter using claude-agent-sdk.

Target key: "sethlans.agent.architect"

This is the production capability: drives a single Sethlans subagent in isolation
as the main agent via the Claude Agent SDK (query() API).

IMPORTANT: This adapter is gated behind the optional extra [level-a].
  - If ANTHROPIC_API_KEY is not set, raises RuntimeError on instantiation.
  - If claude-agent-sdk is not installed, raises ImportError with a clear message.
  - Live tests should be decorated with @pytest.mark.live and skipped when key is absent.

SDK note: The exact claude-agent-sdk API is verified against the installed version
at build time. Since the SDK is not installed in this environment, the code is
structured per the documented intent (query() + hooks), with lazy import guards.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from ludus.adapters.base import Adapter
from ludus.models import Artifact, RunResult, Tokens, Trace
from ludus.scenario import Context, RunConfig, ScenarioInput

_DEFAULT_AGENT_PATH = Path.home() / ".claude" / "agents" / "seth-architect.md"


def _parse_agent_md(path: Path) -> dict[str, Any]:
    """Parse a subagent .md file (YAML front-matter + system-prompt body).

    Returns dict with 'name', 'model', 'description', 'system_prompt'.
    """
    text = path.read_text(encoding="utf-8")
    meta: dict[str, Any] = {}
    system_prompt = text

    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            import yaml

            front_matter = text[3:end].strip()
            meta = yaml.safe_load(front_matter) or {}
            system_prompt = text[end + 3 :].strip()

    return {
        "name": meta.get("name", path.stem),
        "model": meta.get("model", "claude-opus-4-5"),
        "description": meta.get("description", ""),
        "system_prompt": system_prompt,
    }


class SingleSubagentAdapter(Adapter):
    """Drives a single Sethlans subagent via claude-agent-sdk as the main agent.

    Requires:
      - ANTHROPIC_API_KEY environment variable
      - claude-agent-sdk installed (optional extra [level-a])
    """

    def __init__(
        self,
        agent_path: str | Path | None = None,
    ) -> None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "SingleSubagentAdapter requires ANTHROPIC_API_KEY to be set. "
                "Use MockAdapter (target: mock.architect) for keyless runs."
            )
        self._agent_path = Path(agent_path) if agent_path else _DEFAULT_AGENT_PATH
        if not self._agent_path.exists():
            raise FileNotFoundError(f"Subagent definition not found: {self._agent_path}")

        try:
            import claude_agent_sdk as _sdk  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "claude-agent-sdk is not installed. "
                "Install the [level-a] optional extra: uv add 'ludus[level-a]'"
            ) from exc

        self._agent_def = _parse_agent_md(self._agent_path)

    def run(
        self,
        scenario_input: ScenarioInput,
        context: Context,
        run_config: RunConfig,
    ) -> RunResult:
        """Invoke the subagent and collect the RunResult.

        Hooks capture PreToolUse/PostToolUse events into trace.tool_calls.
        ResultMessage provides cost/tokens/latency/session.
        """
        try:
            return self._run_live(scenario_input, context, run_config)
        except Exception as exc:
            return RunResult(
                artifact=Artifact(type="error", text=str(exc)),
                trace=Trace(),
                status="error",
                raw={"error": str(exc), "type": type(exc).__name__},
            )

    def _run_live(
        self,
        scenario_input: ScenarioInput,
        context: Context,
        run_config: RunConfig,
    ) -> RunResult:
        import claude_agent_sdk as sdk

        fixture_text = Path(scenario_input.prompt_fixture).read_text(encoding="utf-8")
        model = run_config.model or self._agent_def["model"]

        tool_calls: list[dict[str, Any]] = []
        messages: list[dict[str, Any]] = []
        start_ms = time.time() * 1000

        # Build options — exact kwarg names verified at build time if SDK is installed
        options_kwargs: dict[str, Any] = {
            "system_prompt": self._agent_def["system_prompt"],
            "model": model,
        }
        if run_config.bare:
            # Reproducibility: disable ambient hooks/plugins/MCP/CLAUDE.md
            options_kwargs["bare"] = True

        if run_config.max_budget_usd:
            options_kwargs["max_budget_usd"] = run_config.max_budget_usd

        # Collect all messages via generator
        result_message: Any = None
        try:
            for msg in sdk.query(prompt=fixture_text, **options_kwargs):
                msg_type = type(msg).__name__
                if msg_type == "PreToolUseMessage":
                    tool_calls.append(
                        {
                            "name": getattr(msg, "tool_name", "unknown"),
                            "input": getattr(msg, "tool_input", {}),
                            "phase": "pre",
                        }
                    )
                elif msg_type == "PostToolUseMessage":
                    # Match to last pre-call of same tool name
                    tool_output = getattr(msg, "tool_result", None)
                    tool_name = getattr(msg, "tool_name", "unknown")
                    for tc in reversed(tool_calls):
                        if tc["name"] == tool_name and "output" not in tc:
                            tc["output"] = str(tool_output) if tool_output else None
                            tc["phase"] = "post"
                            break
                elif msg_type in ("AssistantMessage", "TextMessage"):
                    content = getattr(msg, "content", "") or getattr(msg, "text", "")
                    messages.append({"role": "assistant", "content": str(content)})
                elif msg_type == "ResultMessage":
                    result_message = msg

        except Exception as exc:
            # Catch budget exceeded or other SDK errors
            error_str = str(exc)
            status: str = "error"
            if "budget" in error_str.lower():
                status = "budget_exceeded"
            return RunResult(
                artifact=Artifact(type="error", text=error_str),
                trace=Trace(
                    tool_calls=_build_tool_calls(tool_calls),
                    latency_ms=time.time() * 1000 - start_ms,
                ),
                status=status,  # type: ignore[arg-type]
                raw={"error": error_str},
            )

        latency_ms = time.time() * 1000 - start_ms

        # Harvest from ResultMessage
        cost_usd = 0.0
        tokens = Tokens()
        session_id: str | None = None
        artifact_text = ""

        if result_message is not None:
            cost_usd = float(getattr(result_message, "cost_usd", 0.0) or 0.0)
            session_id = str(getattr(result_message, "session_id", "") or "")
            result_text = getattr(result_message, "result", "")
            artifact_text = str(result_text) if result_text else ""
            usage = getattr(result_message, "usage", None)
            if usage:
                tokens = Tokens(
                    input=int(getattr(usage, "input_tokens", 0) or 0),
                    output=int(getattr(usage, "output_tokens", 0) or 0),
                    cache_read=int(getattr(usage, "cache_read_input_tokens", 0) or 0),
                    cache_write=int(getattr(usage, "cache_creation_input_tokens", 0) or 0),
                )

        # Check budget breach
        if run_config.max_budget_usd and cost_usd > run_config.max_budget_usd:
            status_val: str = "budget_exceeded"
        else:
            status_val = "completed"

        return RunResult(
            artifact=Artifact(
                type="breakdown",
                text=artifact_text or "\n".join(m["content"] for m in messages),
            ),
            trace=Trace(
                tool_calls=_build_tool_calls(tool_calls),
                tokens=tokens,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                session_id=session_id or None,
                messages=messages,
            ),
            status=status_val,  # type: ignore[arg-type]
            raw={"result_message_type": type(result_message).__name__ if result_message else None},
        )


def _build_tool_calls(raw_calls: list[dict[str, Any]]) -> list[Any]:
    from ludus.models import ToolCall

    return [
        ToolCall(
            name=tc.get("name", "unknown"),
            input=tc.get("input", {}),
            output=tc.get("output"),
            phase=tc.get("phase"),
        )
        for tc in raw_calls
    ]
