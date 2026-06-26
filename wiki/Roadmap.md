# Roadmap

Incremental milestones. Each one names a crisp deliverable, entry/exit criteria, and
which invocation mechanism ([Adapters](Adapters)) it exercises. Terms in
[Vocabulary](Vocabulary); open decisions in [Open Questions](Open-Questions).

## M0 — Charter *(current)*

- **Deliverable:** vocabulary, domain model, this elaborated documentation, wiki published.
- **Exit:** team agrees on the [`RunResult`](Architecture#21-the-runresult-contract-load-bearing)
  envelope and the [Open Questions](Open-Questions) defaults/decisions (O1–O5).

## M1 — Walking skeleton — **isolated Architect subagent via SDK**

- **Deliverable:** ONE real scenario on ONE target = the **Architect subagent** run in
  isolation via the `SingleSubagentAdapter`, with ONE deterministic check
  (structure/contract) + ONE LLM-judge (rubric), and a console report. `RunResult`
  populated with cost/tokens/latency/tool-calls.
- **Entry:** read access to the Sethlans Architect definition; one known-good story fixture.
- **Exit:** `ludus run scenarios/architect/…` prints score + cost; the rerun is
  reproducible (pinned model / `--bare`-equivalent); the `RunResult` schema validates.
- **Mechanism:** Agent SDK as-main-agent + hooks for the tool-call trace.

**Why the isolated subagent, not the full pipeline, as the skeleton:**

1. **Cheaper & faster** — one phase, not six; tighter feedback loop, lower token burn
   while the harness itself is still unstable.
2. **Deterministic surface** — isolated input (fixture) → isolated output; no upstream
   noise, so a failing eval means a harness bug or a real agent regression, not phase-4
   contamination. Far easier to debug a new harness.
3. **It validates the linchpin** — the SDK-as-main mechanism is the riskiest, most novel,
   most "build" part of Ludus. Prove it first. The `PipelineAdapter` is "just" a
   subprocess + JSON parse — lower risk, defer it.
4. **It exercises the most layers** — adapter + deterministic evaluator + LLM-judge +
   `RunResult` + report, end to end, on the smallest possible target.

> Contingency: if SDK access to the Sethlans definitions is blocked at M1, fall back to
> the `PipelineAdapter` as the skeleton — but treat that as a contingency, not the plan.

## M2 — Gate & baseline

- **Deliverable:** Gate policy (`min_pass_rate`, `max_regression_vs_baseline`),
  file-based baseline store, N-run aggregation + variance, regression report.
- **Entry:** M1 producing stable scores.
- **Exit:** rerunning against a stored baseline flags an injected regression; the gate
  returns a CI exit code.
- **Mechanism:** N repetitions; per-run cost cap enforced (`max_budget_usd`).

## M3 — CI integration

- **Deliverable:** a GitHub Action running a suite headless, blocking merge under the gate.
- **Exit:** a PR with a deliberately regressed agent goes red; green otherwise; `--bare`
  reproducibility confirmed in CI.
- **Mechanism:** Pipeline/Subagent adapters in CI, exit-code gate.

## M4 — Coverage + instrumental gates + Level B + Level C

- **Deliverable:** scenarios for ≥ 3 subagents (Level A); the first **Level B**
  full-pipeline scenario via `PipelineAdapter` with per-phase attribution; **Level C**
  contract gates (in-pipeline + injected-fixture); code gates (pytest/lint/Sonar) wired
  as instrumental evaluators on Dev/code artifacts.
- **Exit:** a full `/sethlans` run is scored end-to-end AND each handoff is validated
  against `contracts/handoffs.yaml`.
- **Mechanism:** all five adapters in play; `parent_tool_use_id` + Tabula-file watching
  for phase spans.

## M5 — Generalization beyond Sethlans

- **Deliverable:** Skill/Prompt/Model adapters exercised on a non-Sethlans target; docs
  for "add your own target".
- **Exit:** an external skill evaluated with zero Sethlans-specific code paths.

---

*Footer — back to [Home](Home).*
