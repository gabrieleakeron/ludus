# Open Questions

The original draft's open questions, **re-done** in light of the Claude Code / Agent SDK
research. Split into *resolved* and *genuinely open*. Terms in [Vocabulary](Vocabulary).

## Resolved by the research

| # | Question | Resolution |
|---|---|---|
| R1 | **Headless single-subagent invocation** | **Feasible** via the Agent SDK, instantiating the subagent definition as the **main** agent (`AgentDefinition` + `query()`). Level A is viable from the start — we are *not* forced to begin at Level B. Consequence: Ludus must locate and load Sethlans subagent definition files (→ O7). |
| R2 | **Per-phase cost/trace in the pipeline** | `parent_tool_use_id` + Tabula handoff-file watching give per-phase attribution. `total_cost_usd` / `usage` / `session_id` come free from `--output-format json`. |
| R3 | **Reproducible CI runs** | `--bare` disables ambient hooks/plugins/MCP/CLAUDE.md; pin the model id; use a fixed workspace checkout. |
| R4 | **Structured output for deterministic checks** | SDK `json_schema` output coercion; otherwise parse files written via Tabula. |
| R5 | **Budget enforcement (mechanism)** | `max_budget_usd` (SDK) / monitor `total_cost_usd` (CLI) caps spend per run. The *policy* (what budget) remains a decision → O4. |

## Genuinely open — needs a decision

| # | Question | Default we can ship | Why it needs a decision |
|---|---|---|---|
| O1 | **Implementation language** | **Python** ✅ *(decided)* — `claude-agent-sdk` exists; richest eval ecosystem (Promptfoo/DeepEval/Inspect); pytest gates. | Strategic; affects CI and integration surface. **Decided: Python.** |
| O2 | **Fixture storage for handoffs** | versioned files in-repo under `fixtures/handoffs/<phase>/` + the contract meta-gate | Volume/secrecy: large or client-data artifacts may need an external store. |
| O3 | **Baseline storage** | JSON/Parquet files committed under `baselines/` (git = history & diff for free) at M2; revisit a DB only if volume demands | Affects regression UX; a DB is heavier. Default: file-based. |
| O4 | **N repetitions & token budget** | N=5 for LLM-judge scenarios, N=1 for deterministic-only; per-run `max_budget_usd` cap; a per-suite ceiling | Real money. The budget envelope and acceptable cost/eval are a product call. |
| O5 | **Buy choice for LLM-judge** | start with **one** (recommend Promptfoo or Inspect AI) wrapped behind the Evaluator interface | Picking several early is churn; make one decision now. |
| O6 | **Contract source-of-truth sync** | `tabula-protocol.md` is canonical; `contracts/handoffs.yaml` is derived | Process: who regenerates the YAML when the protocol changes. |
| O7 | **Access to Sethlans internals** | Ludus needs read access to the plugin's subagent definition files | Hard dependency on the Sethlans repo layout/versioning — agree with the Sethlans owners. **In progress:** access being arranged. |

## Decisions taken so far

- **O1 — Language: Python.**
- **M1 walking skeleton: isolated Architect subagent via SDK** (see [Roadmap](Roadmap)).
- **Wiki: English, single source of truth;** `docs/architettura.md` stays as the Italian scratchpad.

## Still to confirm

- **O2/O3** file-based fixtures & baselines in-repo (proposed default).
- **O4** the cost cap and default N.
- **O5** which single LLM-judge tool to start with.
- **O7** the concrete access path to the Sethlans subagent definitions.

---

*Footer — back to [Home](Home).*
