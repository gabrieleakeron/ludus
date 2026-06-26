# Evaluators

An **Evaluator** judges an `artifact` (and sometimes its `trace`) against a scenario's
expectations, producing a [Score / Verdict](Vocabulary). Evaluators only ever see the
[`RunResult`](Architecture#21-the-runresult-contract-load-bearing) `artifact` + `trace`,
never adapter internals — that is what keeps them target-agnostic.

## The four families

| Family | When | Example on Sethlans |
|---|---|---|
| **Deterministic** | structured / verifiable output | the story has all required fields; output matches a JSON schema; a file exists |
| **Instrumental** (gate) | the output is code | `pytest` green, lint clean, coverage ≥ threshold, Sonar/CodeScene OK |
| **LLM-as-judge** | natural-language output | quality/clarity of acceptance criteria; coherence of the task breakdown, scored on a rubric |
| **Human-in-loop** | final judgment / calibration | manual spot-check to tune the LLM judges |

> **Where Sonar/CodeScene fit:** they attach as *instrumental* evaluators **downstream,
> only on artifacts that are code** (Level A-dev and Level B). Process artifacts (stories,
> architecture) need LLM judges instead.

## Level C — handoff-contract validation lives here

Level C (gating the *semilavorati* exchanged between phases) is, technically, a
**deterministic evaluator**. It has a clean home because `tabula-protocol.md` is a formal
contract and the [`PipelineAdapter`](Adapters) already watches handoff files being written.

### Structural contract validation — the `ContractEvaluator`

- Parse `tabula-protocol.md` into a **machine-checkable schema per handoff** (PO→UX,
  UX→Architect, …): required sections/fields, cross-reference rules.
- The `ContractEvaluator` takes a handoff artifact + the phase pair and asserts: required
  sections present, required fields non-empty, cross-references resolve (e.g. every task
  in the Architect output traces back to a PO acceptance criterion). It produces a
  structural score and a hard pass/fail verdict.
- It runs **inline during a Level B run** (validate each handoff as it lands) **and
  standalone** (validate a stored fixture).

**Source of truth:** keep `tabula-protocol.md` as the human contract and a derived
`contracts/handoffs.yaml` (one schema block per phase boundary) as the machine artifact
Ludus consumes. The YAML is generated/kept in sync from the protocol — the protocol is
canonical. (Sync ownership is [Open Question O6](Open-Questions).)

### Known-good fixture injection — isolation

This is what makes Level A *and* fault-localized Level C possible:

- Store curated, contract-passing *semilavorati* as **fixtures**.
- To test phase 5 (Dev) in isolation, the `SingleSubagentAdapter` receives the known-good
  phase-4 artifact as its input instead of running phases 1–4. A defect in the UX phase
  cannot then pollute the score of the Dev phase.
- A fixture is **admissible only if it passes the `ContractEvaluator`** — enforce this at
  fixture-commit time (a meta-gate). This prevents "garbage fixture in → meaningless
  score out".

### Two Level-C modes

| Mode | How | Detects |
|---|---|---|
| **In-pipeline gate** | validate each handoff during a Level B run | real handoff degradation under realistic upstream noise |
| **Injected-fixture gate** | feed a known-good upstream artifact to one downstream phase (Level A) | isolated phase quality, fault-localized |

## Build vs buy

The LLM-judge / assertion / tracing machinery is commodity — see [Build vs Buy](Build-vs-Buy).
Ludus wraps a chosen LLM-judge tool behind this Evaluator interface rather than coupling
to it directly.

---

*Footer — back to [Home](Home).*
