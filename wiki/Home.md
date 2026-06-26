# Ludus AI

**Ludus AI is a test bench for AI systems** — agents, plugins, models, prompts and
skills. It does not *build* agents; it puts them **to the proof** in a repeatable,
measurable way, producing scores, pass/fail gates and regression detection.

> **Status:** design / charter phase (M0). **Pilot use case:** evaluating the
> [Sethlans](#) multi-agent Claude Code plugin.

This wiki is the **canonical source** for Ludus design documentation. It is written in
English; the original Italian working draft lives in `docs/architettura.md` in the repo
and remains a scratchpad until the wiki stabilizes. The wiki pages are generated from
`wiki/*.md` in the repository — see [Publishing](#publishing) below.

---

## Golden path (suggested reading order)

1. **[Vocabulary](Vocabulary)** — the words we use, fixed once so we never argue about
   "hardness" again: Eval, Harness, Scenario, Evaluator, Gate, plus the three test levels.
2. **[Architecture](Architecture)** — the domain model, the layered design, and the
   load-bearing **`RunResult` contract**.
3. **[Adapters](Adapters)** — *how* we invoke each target, and why a single subagent and
   the full pipeline are two physically different mechanisms.
4. **[Evaluators](Evaluators)** — *how* we judge an output: deterministic, instrumental,
   LLM-as-judge, human-in-loop — and where the handoff-contract gate lives.
5. **[Scenario Format](Scenario-Format)** — how a test case is written, in YAML.
6. **[Roadmap](Roadmap)** — M0–M5, what ships at each step, and why M1 starts where it does.
7. **[Open Questions](Open-Questions)** — what is resolved, what still needs a decision.
8. **[Build vs Buy](Build-vs-Buy)** — what Ludus owns vs what it integrates.

---

## What Ludus is, in one paragraph

AI outputs are **non-deterministic**. We therefore do not reason in hard pass/fail on a
single run, but in **scores aggregated over N runs** and — above all — in **regressions**
against a historical baseline. Ludus runs a `Target × Scenario` through an **Adapter**,
captures the produced **artifact** plus its **trace** (tokens, cost, latency, tool calls)
in a uniform **`RunResult`**, hands that to one or more **Evaluators**, aggregates the
**Scores**, and applies **Gates** that the CI consults to block or promote a change.

## The pilot: Sethlans

Sethlans orchestrates `PO → UX → Architect → DevOps → Dev → Reviewer/Tester`. Each phase
produces a *semilavorato* (intermediate artifact) that feeds the next. This gives Ludus
three natural test levels:

- **Level A** — test a single agent in isolation (unit-like).
- **Level B** — test the whole `/sethlans` pipeline end-to-end.
- **Level C** — gate the handoffs *between* phases against a formal contract.

See [Vocabulary](Vocabulary) for the precise definitions.

---

## Publishing

These pages are maintained as Markdown files under `wiki/` in the repository and
synchronized to the GitHub wiki by `.github/workflows/publish-wiki.yml`. Edit the files
in the repo, not the wiki directly — direct edits are overwritten on the next sync.

---

*Footer — back to [Home](Home).*
