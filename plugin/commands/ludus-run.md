---
description: Run a Ludus scenario and report the score, pass-rate and gate verdict.
argument-hint: <scenario_id> [target] [n]
---

Run a scenario against the Ludus backend via MCP.

Arguments (from `$ARGUMENTS`): `<scenario_id> [target] [n]`.

Steps:
1. If no scenario id was given, call `list_scenarios` and ask the user to pick one.
2. Call `run_scenario` with the scenario id (and the optional `target` / `n`
   overrides if provided).
3. Report the result clearly: overall mean score, pass rate, and the gate verdict
   (PASS / FAIL / no gate). Include the per-repetition scores if useful.
4. Mention the run id so the user can inspect it later with `/ludus-runs`.

Runs are synchronous and may take a while for live (non-mock) targets.
