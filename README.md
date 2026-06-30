# Ludus AI

**Ludus AI is a test bench for AI systems** — agents, plugins, models, prompts and
skills. It does not *build* agents; it puts them **to the proof** in a repeatable,
measurable way, producing scores, pass/fail gates and regression detection.

The pilot use case is evaluating [Sethlans](https://github.com/gabrieleakeron/sethlans),
a multi-agent Claude Code orchestration plugin.

**Status:** M0 ✅ charter — M1 ✅ walking skeleton — M2 ✅ gates & baseline — M3 CI integration (planned)

---

## Install

Requires **Python ≥ 3.11** and [uv](https://docs.astral.sh/uv/) (recommended) or pip.

```bash
# editable install with dev dependencies (pytest, ruff)
pip install -e ".[dev]"
```

Optional extras (only needed for live adapters):

| Extra | Installs | When you need it |
|---|---|---|
| `llm` | `anthropic` | Real `llm_judge` evaluator against the Anthropic API |
| `level-a` | `anthropic` + `claude-agent-sdk` | Level-A `SingleSubagentAdapter` (live Sethlans agent) |

```bash
pip install -e ".[dev,llm]"        # add the real LLM judge
pip install -e ".[dev,llm,level-a]"  # add the live Level-A adapter
```

The repo uses **uv**: prefix commands with `uv run` to run inside the managed
virtualenv without activating it.

---

## Quickstart

The bundled scenario uses the `mock.architect` target — no API key required.

### Plain report (no gate check)

```bash
uv run ludus run scenarios/architect/breakdown-login.yaml --no-gate
```

Output:

```
============================================================
  LUDUS REPORT — architetto-scomposizione-login
============================================================
  Target   : mock.architect
  Runs (N) : 5
------------------------------------------------------------
  SCORE SUMMARY
------------------------------------------------------------
  Overall mean score  : 0.8000
  Population variance : 0.000000
  Std deviation       : 0.000000
------------------------------------------------------------
  PER-EVALUATOR MEANS
------------------------------------------------------------
  [contains      ]  mean=1.0000  pass_rate=100%
  [llm_judge     ]  mean=0.4000  pass_rate=0%
  [schema        ]  mean=1.0000  pass_rate=100%
------------------------------------------------------------
  COST / TOKENS / LATENCY
------------------------------------------------------------
  Total cost (USD)   : $0.030670  (mean/run $0.006134)
  Input tokens       : 9,210
  Output tokens      : 3,060
  Total latency (ms) : 21,602  (mean/run 4,320 ms)
  Tool calls         : 15  (mean/run 3.0)
------------------------------------------------------------
  PER-RUN DETAIL
------------------------------------------------------------
  Run  1  score=0.8000  status=completed  ...  llm_judge=0.40(FAIL)
  ...
============================================================
```

### With gate check (demonstrates M2 gate behavior)

```bash
uv run ludus run scenarios/architect/breakdown-login.yaml
echo "Exit code: $?"
```

After the report, the GATE section is appended and the process exits 1:

```
------------------------------------------------------------
  GATE
------------------------------------------------------------
  min_pass_rate                   value=0.0000      threshold=0.9000  => FAIL
  regression                      n/a         threshold=0.0500  => n/a
------------------------------------------------------------
  Overall verdict: FAIL
============================================================
```

```
Exit code: 1
```

This is expected behavior, not a bug: the stub `llm_judge` scores 0.40 < 0.5,
giving a pass_rate of 0% against the scenario's `min_pass_rate: 0.9` gate.
Use `--no-gate` for development/exploration; let the gate run in CI.

---

## CLI reference

```
ludus run SCENARIO [-n N] [-t TARGET] [--update-baseline] [--no-gate]
ludus baseline update SCENARIO [-n N] [-t TARGET]
```

| Flag | Meaning |
|---|---|
| `-n / --repeat N` | Override the scenario `repeat` field |
| `-t / --target T` | Override the scenario `target` field |
| `--update-baseline` | After running, persist aggregate scores as the new baseline |
| `--no-gate` | Skip gate evaluation; always exits 0 |

**Exit codes:** `ludus run` exits `1` if and only if a gate was evaluated and
failed; `0` in all other cases (no `gate:` block, `--no-gate`, or gate passes).
`ludus baseline update` always exits `0` on a successful run (gate not enforced).

---

## Concepts

| Term | Meaning |
|---|---|
| **Eval** | The discipline: measuring AI-system quality |
| **Harness** | The infrastructure that runs a Target against Scenarios and collects results |
| **Target** | What is under test — a single agent, a full pipeline, a skill, a prompt, or a model |
| **Adapter** | The component that knows how to invoke a given Target |
| **Scenario** | One test case: `input` + `context` + `expectations` |
| **Run** | One execution of Target × Scenario — non-deterministic, repeated N times |
| **Artifact** | The output produced, plus the trace (tokens, cost, latency, tool calls) |
| **Evaluator** | Applies a judge to an Artifact — deterministic, instrumental, LLM-as-judge, or human |
| **Score / Verdict** | Numeric score, pass/fail, or rubric result from an Evaluator |
| **Gate** | Threshold policy that turns aggregated Scores into a CI pass/fail |
| **Baseline** | Historical aggregate stored as JSON; used for regression comparison |

AI outputs are **non-deterministic**. Ludus never reasons in single-run pass/fail —
it reasons in **scores aggregated over N runs** and in **regressions vs a baseline**.

For depth on each concept, see the [wiki](../../wiki/Vocabulary).

---

## Documentation

Full documentation lives in the **[project wiki](../../wiki)**. Suggested reading:

1. [Getting Started](../../wiki/Getting-Started) — install, run a scenario, understand the report, gates and baselines
2. [Vocabulary](../../wiki/Vocabulary) — precise definitions of every term
3. [Architecture](../../wiki/Architecture) — domain model and layered design
4. [Scenario Format](../../wiki/Scenario-Format) — how test cases are written in YAML
5. [Evaluators](../../wiki/Evaluators) — the four evaluator families
6. [Roadmap](../../wiki/Roadmap) — M0–M5 milestones

The full design model is documented in the [wiki](../../wiki) (see [Architecture](../../wiki/Architecture)).

---

## Development

```bash
uv run pytest          # run the test suite
uv run ruff check .    # lint
uv run ruff format .   # format
```
