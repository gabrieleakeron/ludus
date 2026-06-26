# M1 Analysis — Walking skeleton (isolated Architect subagent via SDK)

Working analysis that turns the [Roadmap](Roadmap)'s **M1** milestone into a concrete,
sequenced build. Terms in [Vocabulary](Vocabulary); the spine is in
[Architecture](Architecture); the two invocation mechanisms in [Adapters](Adapters);
the judging families in [Evaluators](Evaluators); open decisions in
[Open Questions](Open-Questions).

> **Decisions baked into this analysis:** Level A is the plan (O7 access to the Sethlans
> definitions is granted). Python is the language (O1). This document is the analysis
> deliverable for the `m1-analysis` branch — **not** code yet.

## 1. What M1 is (and is not)

From the [Roadmap](Roadmap#m1--walking-skeleton--isolated-architect-subagent-via-sdk):
ONE real scenario on ONE target — the Sethlans **Architect** subagent run *in isolation*
via the `SingleSubagentAdapter` — with **one deterministic check** + **one LLM-judge**,
and a **console report**. The [`RunResult`](Architecture#21-the-runresult-contract-load-bearing)
is populated with cost / tokens / latency / tool-calls.

| | M1 includes | M1 explicitly defers |
|---|---|---|
| Adapters | `SingleSubagentAdapter` (Level A) only | Pipeline / Skill / Prompt / Model adapters (M4–M5) |
| Evaluators | one deterministic + one LLM-judge | instrumental/code gates, Level-C contract eval (M4) |
| Aggregation | `repeat` N, mean + variance | gate policy, baseline store, regression (M2) |
| Output | console report | CI exit-code gate, GitHub Action (M2–M3) |

The point of M1 is **not** breadth — it is to prove the riskiest layer (SDK-as-main-agent
+ trace capture) end-to-end on the smallest possible target, exercising **every layer
once**: adapter → deterministic evaluator → LLM-judge → `RunResult` → report.

## 2. Component decomposition

Eight pieces. They map 1:1 onto the layers in [Architecture §2](Architecture#2-layered-architecture).

| # | Component | M1 responsibility | Risk |
|---|---|---|---|
| 1 | **`RunResult` model** | Pydantic model of the `{artifact, trace, status, raw}` envelope; schema validates | low — but **load-bearing**, freeze first |
| 2 | **`SingleSubagentAdapter`** | Load Architect `.md` → `AgentDefinition` as **main**; `query()` with `initialPrompt`=fixture; hooks capture tool calls; `ResultMessage` → cost/tokens; `max_budget_usd` cap | **high** — the novel, owned capability |
| 3 | **Scenario loader** | Parse the [Scenario YAML](Scenario-Format), resolve `target`→adapter, materialize `input`/`context` | medium — format is still draft |
| 4 | **Deterministic evaluator** | one check: `schema` (`must_have_fields`) or `contains`; sees only `artifact`+`trace` | low |
| 5 | **LLM-judge evaluator** | one rubric over the Architect output, behind the Evaluator interface | medium — tool choice (O5) |
| 6 | **Console report** | print score + cost/tokens/latency/tool-call count; mean + variance over N | low |
| 7 | **CLI `ludus run`** | entry point wiring 3→2→{4,5}→6; reproducibility flags | low |
| 8 | **Fixture** | one known-good Architect input story (+ optional repo skeleton) | blocked on Sethlans layout |

## 3. The `RunResult` for M1 (minimal but honest)

M1 must populate, at minimum:

- `artifact.text` **or** `artifact.structured_json` (if the SDK `json_schema` path is used
  for the deterministic check — R4).
- `trace.tool_calls[]` — from `PreToolUse`/`PostToolUse` hooks (the explicit M1
  deliverable "tool-calls").
- `trace.tokens`, `trace.cost_usd`, `trace.latency_ms`, `trace.session_id` — from the
  SDK `ResultMessage`.
- `status` ∈ `{completed, budget_exceeded, timeout, error}`.

Discipline ([Architecture §2.1](Architecture#21-the-runresult-contract-load-bearing)):
evaluators read only `artifact` + `trace`. SDK-specific blobs go in `raw`, never read by a
judge. This is the contract that lets M2+ swap in other adapters with zero evaluator
changes — get it right now even though M1 has only one adapter.

## 4. Build sequence (vertical spike, not layer-by-layer)

```
(1) RunResult model
        │
        ▼
(2) SingleSubagentAdapter  ← SPIKE FIRST: prove SDK-as-main + hook trace on the real Architect
        │
        ├────────────► (3) Scenario loader ──► (7) CLI `ludus run`
        │
        ├────────────► (4) deterministic evaluator
        └────────────► (5) LLM-judge evaluator ──► (6) console report
```

**Spike before scaffolding.** The single highest-uncertainty question is *"can we load the
Architect definition as the main agent and capture a faithful tool-call trace + cost?"*
Answer it with a throwaway script (component 2 against a hard-coded fixture) **before**
building the loader, evaluators, and CLI around it. If the spike fails, the
[Roadmap contingency](Roadmap#m1--walking-skeleton--isolated-architect-subagent-via-sdk)
(fall back to `PipelineAdapter` / Level B as the skeleton) triggers here — cheaply, before
sunk cost.

## 5. The `SingleSubagentAdapter` — the linchpin (detail)

Per [Adapters](Adapters), the Level-A mechanism. M1 must:

1. **Locate + parse** the Architect subagent definition (system prompt, allowed tools,
   model). *Path/format to confirm against the Sethlans repo — see §9.*
2. **Promote it to main** — instantiate as `AgentDefinition` and drive it via the Agent
   SDK `query()` with the fixture as the initial prompt. (There is no CLI flag to target a
   single subagent — this is *why* Level A needs the SDK; see
   [Build vs Buy](Build-vs-Buy#why-the-sdk-is-the-foundation-not-the-cli-alone).)
3. **Instrument** tool calls via `PreToolUse`/`PostToolUse` hooks → `trace.tool_calls[]`.
4. **Harvest** cost/tokens/latency/session from the terminal `ResultMessage`.
5. **Reproducibility** — pin the model id and disable ambient hooks/plugins/MCP/CLAUDE.md
   (the SDK equivalent of `--bare`; R3). Without this the rerun is not deterministic enough
   to satisfy the M1 exit criterion.
6. **Budget** — enforce `max_budget_usd`; on breach set `status = budget_exceeded`.

> The exact `claude-agent-sdk` API surface (option names, message types, hook signatures)
> must be verified against the **installed SDK version** at build time — treat the names in
> [Adapters](Adapters) as the documented intent, not a frozen contract.

## 6. Evaluators for M1 (one each)

- **Deterministic** — prefer the `schema` check (`must_have_fields`) if we coerce the
  Architect output via SDK `json_schema` (R4); otherwise `contains` over the text. One
  check is enough for the skeleton.
- **LLM-judge** — one rubric scoring the Architect's task breakdown (e.g. *covers all
  acceptance criteria, choices justified, no orphan tasks*), wrapped **behind the Evaluator
  interface**. The concrete tool (Promptfoo / Inspect AI / DeepEval) is
  [O5](Open-Questions) and must be picked for M1 — see §8.

Both consume `RunResult` only. The rubric file lives under `rubrics/architect.md` as in the
[Scenario-Format example](Scenario-Format#example--level-a-single-subagent-isolated).

## 7. Scenario + fixture (the one real test case)

The M1 scenario is the Level-A example already drafted in
[Scenario-Format](Scenario-Format#example--level-a-single-subagent-isolated):
`scenarios/architect/breakdown-*.yaml`, `target: sethlans.agent.architect`, an
`input.prompt_fixture` pointing at a **known-good upstream story**, `repeat: 5`, the two
expectations above. M1 validates this draft format against a first real file — expect to
adjust it.

The fixture is a curated, contract-passing story. (In M1 there is no `ContractEvaluator`
yet, so admissibility is by manual curation; the meta-gate arrives with Level C in M4.)

## 8. Decisions M1 forces now

| Ref | Decision needed for M1 | Recommended default |
|---|---|---|
| [O5](Open-Questions) | Which **single** LLM-judge tool | Promptfoo or Inspect AI, wrapped behind the Evaluator interface |
| [O4](Open-Questions) | `repeat` N + per-run `max_budget_usd` | N=5 (LLM-judge scenario); set a small per-run USD cap |
| [O7](Open-Questions) | Concrete path to the Architect definition | resolve via §9 against the Sethlans repo |

O1 (Python) is decided; O2/O3 (fixture/baseline storage) do not bind until M2.

## 9. To confirm against the Sethlans repo *(this session could not read it — scope-limited to `ludus`)*

Before/while building component 2 and 8, confirm on `gabrieleakeron/sethlans`:

1. **Where** the Architect subagent definition lives and its **file format** (the `.md`
   front-matter: system prompt, `tools`, `model`).
2. The **shape of the Architect's expected output** — to write the deterministic
   `must_have_fields` / `json_schema` and the rubric truthfully.
3. A **known-good input story** to seed the fixture (an upstream PO/UX *semilavorato*).
4. `tabula-protocol.md` location — not needed for M1 (Level A), but it anchors M4's
   Level-C work; note it now.

## 10. Definition of done (M1 exit checklist)

- [ ] `ludus run scenarios/architect/<scenario>.yaml` prints **score + cost** to console.
- [ ] `RunResult` schema **validates** on a real run (artifact + populated trace).
- [ ] `trace` carries tool-calls, tokens, cost, latency, session id.
- [ ] Rerun is **reproducible** (pinned model + `--bare`-equivalent).
- [ ] One deterministic check **and** one LLM-judge both run and contribute to the score.
- [ ] Mean + variance reported over `repeat` N.

When all six hold, M1 is met and [M2](Roadmap#m2--gate--baseline) (gate + baseline) can
start on a stable score.

---

*Footer — back to [Home](Home).*
