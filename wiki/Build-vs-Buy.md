# Build vs Buy

What Ludus **owns** versus what it **integrates**. The principle: build the thin, novel,
high-value layer; integrate mature commodity tooling for everything else. Terms in
[Vocabulary](Vocabulary).

## The split

- The **upper layer** — running a *Claude Code plugin with subagents* repeatably,
  isolating a single subagent, injecting fixtures between phases, reading Tabula traces —
  is **niche**. Existing eval frameworks test prompts/models/API calls, not "multi-agent
  Claude Code plugin invocations". **We build this** — it is Ludus's own value.
- The **lower layer** — LLM-as-judge, scoring, tracing, code gates — is **commodity**:
  good, mature tools already exist.

## Recommendation: hybrid

Ludus builds the harness + scenario model + adapters for Sethlans, and **integrates**
(does not reinvent) the rest.

| Layer | Decision | Candidates to evaluate |
|---|---|---|
| Claude Code harness/adapter | **Build** | Claude Agent SDK (`claude-agent-sdk`) — **confirmed as the build foundation** (it is what makes Level A possible; see [Adapters](Adapters)) |
| Scenario format + gates | **Build** | (this is our contract — see [Scenario Format](Scenario-Format)) |
| LLM-as-judge / assertions | Buy / integrate | Promptfoo, DeepEval, Inspect AI — **start with one** ([Open Question O5](Open-Questions)) |
| Tracing / observability | Buy / integrate | Langfuse, Phoenix |
| Code gates | Buy / integrate | pytest, lint, SonarQube, CodeScene |

## Why the SDK is the foundation, not the CLI alone

The research confirmed that isolating a single subagent (Level A) is **only** possible by
promoting its `AgentDefinition` to be the main agent via the SDK — there is no CLI flag
for it. The CLI (`claude -p`) covers the full-pipeline case (Level B). Both are wrapped
behind the uniform [`RunResult`](Architecture#21-the-runresult-contract-load-bearing) so
the buy/integrate layers above never see which mechanism produced the result.

> Keep the integrations **behind our own interfaces** (the Evaluator interface for
> judges, the Adapter interface for invocation). That way swapping Promptfoo for Inspect,
> or Langfuse for Phoenix, is a local change, not a rewrite.

---

*Footer — back to [Home](Home).*
