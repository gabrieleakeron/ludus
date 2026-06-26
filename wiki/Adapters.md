# Adapters

An **Adapter** turns a `Target × Scenario` into a [`RunResult`](Architecture#21-the-runresult-contract-load-bearing).
This page documents the adapter interface and the five concrete adapters. Terms are in
[Vocabulary](Vocabulary).

## The adapter interface

A narrow interface with one core method:

```
Adapter.run(scenario_input, context, run_config) -> RunResult
```

- **`scenario_input`** — the prompt/fixture(s) that drive the target (a brief, a story, a
  use-case description, an upstream *semilavorato*).
- **`context`** — filesystem state to materialize before the run (repo skeleton, injected
  upstream artifacts) plus env (model override, MCP on/off).
- **`run_config`** — `repeat` N, `max_budget_usd`, timeout, `bare` (reproducibility)
  flag, optional output `json_schema`.
- **returns** — a [`RunResult`](Architecture#21-the-runresult-contract-load-bearing).

## Why two mechanisms, not one

Researching the current Claude Code / Agent SDK docs surfaced the linchpin constraint:

- **There is no CLI flag to directly target a single subagent.** Subagents are normally
  reachable only via the Agent/Task tool, when the *main* agent decides to delegate.
- Therefore, to test a single subagent **in true isolation**, you must instantiate its
  definition **as the main agent** via the Claude Agent SDK. This is a different runtime
  from the `claude -p` binary used for the full pipeline.

So Level A and Level B are **two distinct adapter implementations**, not one parametrized
adapter.

## The five concrete adapters

| Adapter | Mechanism | What it must capture | Notes |
|---|---|---|---|
| **SingleSubagentAdapter** (Level A) | Agent SDK: load subagent `.md` definition → `AgentDefinition` as **main** agent; `query()` with `initialPrompt` = fixture | artifact = final assistant output (optionally `json_schema`-coerced); trace from message iteration + `ResultMessage` (cost/tokens); tool calls via `PreToolUse`/`PostToolUse` hooks | Must parse the Sethlans agent definition (system prompt, allowed tools, model). `max_budget_usd` cap. The novel, owned capability. |
| **PipelineAdapter** (Level B) | `claude -p "/sethlans <usecase>" --output-format stream-json --bare` (subprocess) | final product (files in workspace) + full stream trace; `total_cost_usd`, `usage`, `session_id` from result JSON; per-phase attribution via `parent_tool_use_id` | `--bare` for CI reproducibility (no ambient hooks/CLAUDE.md). Workspace = throwaway git checkout. |
| **SkillAdapter** | `claude -p "/<skill> …"` headless, or SDK with the skill loaded | artifact + trace, same envelope | Thin variant of Pipeline; differs only in the invocation string and which plugin/skill is enabled. |
| **PromptAdapter** | SDK `query()` or direct Messages API with a templated prompt, no tools | structured/text output + tokens/cost/latency | No tool calls expected; `trace.tool_calls` empty. Cheapest. |
| **ModelAdapter** | Direct Anthropic Messages API call | completion + usage; cost computed from a model pricing table | Pure model-level eval, no agent scaffolding. Useful for "did the model regress" baselines. |

## Per-phase attribution for Level B (the hard part)

Level B is a black box, so the `PipelineAdapter` reconstructs phase boundaries from the
stream, in priority order:

1. **`parent_tool_use_id` chaining** — every tool call emitted inside a delegated
   subagent carries the parent Task tool-use id. Group spans by parent to get a per-phase
   (PO/UX/Architect/…) cost & tool breakdown.
2. **Tabula handoff markers** — Sethlans writes each *semilavorato* to disk via
   `tabula-protocol.md`. The appearance of each handoff file is a reliable phase
   delimiter; the adapter watches the workspace and timestamps writes → phase latency.
3. **Fallback** — text markers in the transcript.

This gives Level B a *per-phase* trace even without subagent isolation — valuable for
"where did the cost/time/error originate" reporting.

## Headless invocation reference (Claude Code / Agent SDK)

- **CLI headless:** `claude -p "<prompt>"` runs non-interactively. `--output-format
  json` returns `result`, `session_id`, `total_cost_usd`, `usage`. `--output-format
  stream-json --verbose` streams the full tool-call trace. `--bare` disables ambient
  hooks/plugins/MCP/CLAUDE.md for reproducible CI runs.
- **Slash commands work headless:** `claude -p "/sethlans …"` triggers the whole pipeline.
- **Python SDK:** `pip install claude-agent-sdk`; `query(prompt, options=ClaudeAgentOptions(
  agents={...: AgentDefinition(...)}, allowed_tools=[...], max_budget_usd=...))` →
  async stream of `SystemMessage`/`AssistantMessage`/`ResultMessage`. `output_format =
  {"type": "json_schema", "schema": {...}}` coerces structured output. `parent_tool_use_id`
  on messages attributes spans to subagents. Hooks (`PreToolUse`/`PostToolUse`) instrument
  tool calls.

> **Dependency:** the `SingleSubagentAdapter` needs read access to the Sethlans subagent
> definition files. Tracked in [Open Questions](Open-Questions) (O7).

---

*Footer — back to [Home](Home).*
