---
description: Create or modify a Ludus scenario interactively, then push it to the backend.
argument-hint: [scenario_id]
---

Guide the user through authoring a Ludus scenario YAML and persist it via MCP.
This command never runs the scenario — only creates/updates it.

## 1. Mode: create vs modify

- If `$ARGUMENTS` contains a scenario id, call `get_scenario` with that id.
  - Found -> **modify mode**: show the current `yaml_source` and ask what to change.
  - 404 -> tell the user no scenario with that id exists yet, and ask whether to
    create it fresh under that id (**create mode**) or stop.
- If `$ARGUMENTS` is empty, ask the user whether they want to create a new
  scenario or modify an existing one. For modify, call `list_scenarios` and let
  them pick an id, then `get_scenario` to load it.

## 2. Target step

Call `list_targets` and split the results by the `runnable` flag:

- **Runnable** (`runnable: true`) — real adapters, safe to reference for a
  scenario the user intends to run today. Present these first.
- **Declared / authoring-only** (`runnable: false`) — present separately,
  labelled "authoring only — cannot be run until a core adapter exists".

Ask the user to pick a target key from this list.

If the target they want isn't in either list, do **not** invent or silently
accept an arbitrary key. Offer to declare it with `register_target(key,
description, requires_api_key)`, and warn clearly *before* calling it that the
new target will be **non-runnable** until a real adapter is implemented for
that key — it will only be usable to author/save scenarios, not to execute
them. If `register_target` fails (400 invalid key, 409 the key already names a
runnable adapter), show the error detail and let the user pick a different key
or use the existing adapter directly.

## 3. Compose the scenario YAML

Collect fields conversationally and build one YAML document (see the scenario
format in the project's `CLAUDE.md` / `scenarios/architect/breakdown-login.yaml`
for reference shape):

- `id` (required) — in modify mode this must match the scenario being edited.
- `target` (required) — the key chosen in step 2.
- `description` (optional).
- `repeat` (optional, default 1) — how many repetitions to estimate stability.
- `input.prompt_fixture` (required) — path to the prompt fixture file.
- `context.files` (optional) — list of upstream file paths.
- `run_config` (optional) — e.g. `max_budget_usd`, `model`, `bare`.
- `expectations` (optional list) — each item one of:
  - `type: schema` with `must_have_fields: [...]`
  - `type: contains` with `any_of: [...]`
  - `type: llm_judge` with `rubric: <path>` and `pass_threshold: <0..1>`
- `gate` (optional) — `min_pass_rate`, `max_regression_vs_baseline`.

Remind the user that fixture/context/rubric paths are resolved **on the
backend host**, not on their local machine — a path that looks valid locally
may not exist there.

Do light sanity checks only (e.g. `id`/`target`/`input.prompt_fixture` present,
`expectations[].type` is one of the three known kinds). Do not try to fully
reimplement scenario validation — the backend is the source of truth and will
reject anything malformed when you persist it.

Render the composed YAML and ask the user to confirm before saving, or adjust
any field.

## 4. Persist

- Create mode -> call `create_scenario(yaml_source)`.
- Modify mode -> call `update_scenario(scenario_id, yaml_source)`.

On success, confirm the returned scenario id and print a short summary:
target, repeat count, number of expectations, and whether the target is
runnable (cross-reference against the `list_targets` result from step 2).

On failure, the backend's 400/404/409 surfaces as a `RuntimeError` whose
message already contains the clean detail (e.g. `Validation failed: Ludus API
error (400): <reason>`). Show that message as-is to the user — do not paraphrase
away the reason — and let them fix the relevant field and retry from step 3.
Common cases: 400 malformed YAML/schema violation, 404 `update_scenario` on an
id that doesn't exist (offer to switch to create mode), 409 from
`register_target` on a key that collides with a runnable adapter.

## 5. Do not auto-run

Never call `run_scenario` from this command. Once the scenario is saved,
mention it can be executed either from the board SPA or by calling the
`run_scenario` MCP tool directly with its id.

## Unreachable backend/MCP

If any tool call fails to connect at all (not a clean 4xx from the backend,
but a connection failure), tell the user the Ludus backend or MCP server is
probably not running and to start them (`docker compose up`, or run the
backend + MCP locally) before retrying.
