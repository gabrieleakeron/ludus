---
description: List recent Ludus runs, or show the detail of one run by id.
argument-hint: [run_id]
---

Inspect Ludus run history via MCP.

- If `$ARGUMENTS` contains a run id, call `get_run` and present the detail:
  target, N, overall mean, pass rate, gate verdict, and a per-repetition breakdown
  (status, score, cost, latency, tokens).
- Otherwise call `list_runs` and present the recent runs as a table (id, scenario,
  target, overall mean, pass rate, gate).

Offer to re-run a scenario with `/ludus-run` if the user wants a fresh evaluation.
