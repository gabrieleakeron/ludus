# Architecture

This is the spine of Ludus. [Adapters](Adapters), [Evaluators](Evaluators) and the
[Scenario Format](Scenario-Format) hang off it. Terms used here are defined in
[Vocabulary](Vocabulary).

## 1. Domain model

The central entities, independent of technology:

```
Suite ──< Scenario ──< Run ──> Artifact
                         │
                         └──< Evaluation ──> Score/Verdict
Gate (policy) ── applies thresholds to ──> Score ──> Report
Target ── is what the Run executes (agent | pipeline | skill | prompt | model)
```

- **Target** — *what* we put to the proof. Behind it: an **Adapter** that knows how to
  invoke it ([Adapters](Adapters)).
- **Scenario** — a test case: `input` (use case), `fixtures/context` (upstream
  artifacts, files, mocks), and `expectations` (assertions + rubrics).
- **Run** — a single `Target × Scenario` execution. Non-deterministic → **N repetitions**.
- **Artifact** — the output produced + the **trace** (steps, tool calls, tokens, cost, latency).
- **Evaluation / Evaluator** — applies one or more judges to the artifact.
- **Score / Verdict** — numeric score, pass/fail, rubric outcome.
- **Gate** — a threshold policy ("≥ 90% of scenarios pass", "no regression > 5% vs
  baseline"). The CI consults it to block/promote.
- **Report** — aggregated results + comparison against the **baseline** (regressions).

**Guiding principle:** because outputs are non-deterministic, we reason in **aggregated
scores over N runs** and in **regressions vs a historical baseline**, not in single-run
pass/fail.

## 2. Layered architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  CLI / CI (GitHub Actions)  ── orchestration, gates, exit code     │
├─────────────────────────────────────────────────────────────────┤
│  Reporting & Baseline  ── aggregated scores, trends, regressions   │
├─────────────────────────────────────────────────────────────────┤
│  Evaluators (judges)                                               │
│   • Deterministic  (regex/contains, JSON schema, file exists)      │
│   • Instrumental   (compiles, tests, coverage, lint, Sonar)        │
│   • LLM-as-judge   (rubrics over natural-language artifacts)       │
│   • Human-in-loop  (capture manual review, optional)               │
├─────────────────────────────────────────────────────────────────┤
│  Harness  ── runs Scenario × Target, N repetitions, collection     │
├─────────────────────────────────────────────────────────────────┤
│  Adapters (how I invoke the Target)                                │
│   • SingleSubagent  → Agent SDK (AgentDefinition AS MAIN)  [Lvl A] │
│   • Pipeline /sethlans → claude -p --output-format stream-json [B] │
│   • Skill           → claude -p "/skill"                           │
│   • Prompt          → SDK query() / Messages API                   │
│   • Model           → Messages API directly                        │
│   ── all return the same RunResult { artifact, trace } ────────────│
├─────────────────────────────────────────────────────────────────┤
│  Scenario store  ── scenario definitions + fixtures (YAML/files)   │
└─────────────────────────────────────────────────────────────────┘
```

> **Three levels → two mechanisms.** Level A (isolated single subagent) is only
> achievable by promoting the subagent's `AgentDefinition` to be the **main** agent via
> the Claude Agent SDK — there is no CLI flag to target one subagent. Level B is a
> headless `claude -p "/sethlans …"` subprocess. They are different runtimes, hence two
> distinct adapters. See [Adapters](Adapters).

## 2.1 The `RunResult` contract (load-bearing)

This is the most important single abstraction in Ludus. Every adapter, regardless of the
underlying mechanism, returns the **same envelope**:

```
RunResult {
  artifact: {
    type            # code | story | breakdown | mockup | text | ...
    files[]         # produced files (path + content/ref)   — OR
    text            # free-text output                       — OR
    structured_json # schema-coerced output (SDK json_schema)
  }
  trace: {
    tool_calls[]    # { name, input, output, parent_tool_use_id, phase? }
    tokens          # { input, output, cache_read, cache_write }
    cost_usd
    latency_ms
    session_id
    messages[]      # full transcript, for LLM-judge / debugging
  }
  status            # completed | budget_exceeded | timeout | error
  raw               # adapter-specific blob, kept for forensics, NEVER read by evaluators
}
```

**The discipline that makes this work:** evaluators only ever see `artifact` + `trace`,
never adapter internals. That is what lets a deterministic check, an LLM-judge, or a code
gate run **identically** whether the target was a single subagent, the full pipeline, a
bare prompt, or a raw model. When in doubt, add to `trace`, not to `raw`.

## 3. End-to-end flow (example: testing the Architect agent)

1. **Scenario** — input = a known-good story; expectations = a rubric ("the breakdown
   covers all acceptance criteria", "technical choices are justified", "no orphan tasks")
   + structural checks.
2. **Adapter** — the `SingleSubagentAdapter` instantiates the Sethlans Architect
   definition as the main agent (SDK), passing the fixture as the initial prompt.
3. **Harness** — runs the run N times, saves `RunResult` (artifact + trace).
4. **Evaluators** — structural check (deterministic) + LLM-as-judge on the rubric.
5. **Score** — mean over N runs + variance (stability).
6. **Gate** — compare to baseline → pass/fail.
7. **Report** — per-scenario table, regression evidence.

---

*Footer — back to [Home](Home).*
