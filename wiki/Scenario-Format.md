# Scenario Format

A **Scenario** is a test case stored as YAML in the scenario store, plus any fixtures it
references. Terms are in [Vocabulary](Vocabulary); the `target` field selects an
[Adapter](Adapters); `expectations` are run by [Evaluators](Evaluators).

> The format below is a **draft to validate** against the first real scenarios in M1.

## Anatomy

```yaml
id: <unique-scenario-id>
target: <adapter-selector>     # which Adapter to use, e.g. sethlans.agent.architect
description: <human description>
repeat: 5                      # N repetitions (non-determinism)

input:
  prompt_fixture: <path>       # the driving input (brief / story / use case)

context:
  files:
    - <path-or-dir>            # repo skeleton, injected upstream artifacts

expectations:
  - type: schema               # deterministic
    must_have_fields: [...]
  - type: contains
    any_of: [...]
  - type: llm_judge            # rubric-based
    rubric: <path>
    pass_threshold: 0.8

gate:
  min_pass_rate: 0.9           # ≥ 90% of runs pass
  max_regression_vs_baseline: 0.05
```

## Example — Level A (single subagent, isolated)

```yaml
# scenarios/architect/breakdown-login.yaml
id: architect-breakdown-login
target: sethlans.agent.architect       # → SingleSubagentAdapter (SDK as main agent)
description: The Architect breaks the "user login" story into coherent tasks
repeat: 5

input:
  prompt_fixture: fixtures/stories/login.md     # known-good upstream story

context:
  files:
    - fixtures/repo-skeleton/                    # state of the repo upstream

expectations:
  - type: schema                                 # deterministic
    must_have_fields: [tasks, rationale]
  - type: contains
    any_of: ["FastAPI", "endpoint", "auth"]
  - type: llm_judge                              # rubric
    rubric: rubrics/architect.md
    pass_threshold: 0.8

gate:
  min_pass_rate: 0.9
  max_regression_vs_baseline: 0.05
```

## Example — Level B (full pipeline, end-to-end)

```yaml
# scenarios/pipeline/login-feature.yaml
id: pipeline-login-feature
target: sethlans.pipeline               # → PipelineAdapter (claude -p "/sethlans" --bare)
description: The whole /sethlans pipeline implements the "user login" feature
repeat: 3                                # pipeline runs are expensive → lower N

input:
  prompt_fixture: fixtures/usecases/login.md

context:
  files:
    - fixtures/repo-skeleton/

expectations:
  - type: code_gate                      # instrumental: runs in the produced workspace
    checks: [pytest, lint, coverage>=0.8]
  - type: contract                       # Level C: validate each handoff inline
    against: contracts/handoffs.yaml
  - type: llm_judge
    rubric: rubrics/feature-acceptance.md
    pass_threshold: 0.8

gate:
  min_pass_rate: 0.8
  max_regression_vs_baseline: 0.05
```

## Fixtures and contract injection

- **Fixtures** (`fixtures/…`) hold known-good inputs and upstream *semilavorati*. To test
  a downstream phase in isolation, point a Level-A scenario's `input.prompt_fixture` /
  `context.files` at a known-good upstream artifact instead of running earlier phases.
- A fixture used as an upstream artifact must pass the
  [`ContractEvaluator`](Evaluators#level-c--handoff-contract-validation-lives-here)
  before it is admissible.

---

*Footer — back to [Home](Home).*
