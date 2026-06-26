# Vocabulary

This page is the **canonical anchor** for Ludus terminology. Other pages link *here*
rather than redefining terms. We fix this vocabulary explicitly to avoid the ambiguity
of words like "hardness" or "test".

## Core discipline

| Term | Meaning in Ludus |
|---|---|
| **Eval** | The discipline: measuring the quality of an AI system. |
| **Harness** | The infrastructure that *runs* the system over scenarios and collects results — the "test runner". |
| **Scenario** | A test case: `input + context → expected output / criteria`. |
| **Evaluator** (Judge / Check) | What judges an output against expectations. |
| **Gate** | The rule that turns scores into pass/fail — what the CI consults. |

## Domain entities

| Term | Meaning |
|---|---|
| **Target** | *What* we put to the proof: a single agent, the whole pipeline, a skill, a prompt, or a model. Behind it sits an **Adapter** that knows how to invoke it. |
| **Adapter** | The component that turns a `Target × Scenario` into a `RunResult`. See [Adapters](Adapters). |
| **Run** | A single execution of `Target × Scenario`. Non-deterministic → we run **N repetitions** to estimate stability. |
| **Artifact** | The output produced (code, story, mockup, task breakdown) — the *semilavorato*. |
| **Trace** | The execution telemetry attached to a run: steps, tool calls, tokens, cost, latency. |
| **RunResult** | The uniform envelope every Adapter returns: `artifact + trace + status`. The contract that lets evaluators stay target-agnostic. See [Architecture](Architecture). |
| **Evaluation** | Applying one or more evaluators to an artifact. |
| **Score / Verdict** | The result: a numeric score, a pass/fail verdict, a rubric outcome. |
| **Baseline** | The stored historical results used to compute regressions. |
| **Report** | Aggregated results + comparison against the baseline. |
| **Fixture** | A curated, known-good input or upstream artifact, used to drive a scenario or to test a downstream phase in isolation. |

## The three test levels

| Level | Kind | What it tests |
|---|---|---|
| **Level A** | unit-like | A **single agent** in isolation: fixed input (fixture) → only its output is judged. |
| **Level B** | e2e | The **full pipeline** (`/sethlans`): the final product is judged. |
| **Level C** | handoff gate | The **artifacts exchanged between phases** must satisfy a formal contract before passing on. |

> **Key insight:** the three levels do **not** map to one invocation mechanism with a
> flag. Level A and Level B use two physically different mechanisms — see
> [Adapters](Adapters).

## Evaluator families

| Family | When | Example on Sethlans |
|---|---|---|
| **Deterministic** | structured / verifiable output | the story has all required fields |
| **Instrumental** (gate) | the output is code | `pytest` green, lint clean, Sonar OK |
| **LLM-as-judge** | natural-language output | quality/clarity of the acceptance criteria |
| **Human-in-loop** | final judgment / calibration | manual spot-check to tune the judges |

See [Evaluators](Evaluators) for detail.

---

*Footer — back to [Home](Home).*
