# Ludus Claude plugin

Connects Claude Code to the **Ludus MCP server** (which in turn talks to the Ludus
backend), and adds convenience slash-commands.

## Contents

- `.claude-plugin/plugin.json` — plugin manifest.
- `.mcp.json` — registers the `ludus` MCP server over **streamable HTTP**
  (default `http://localhost:8765/mcp`).
- `commands/` — slash-commands: `/ludus-scenarios`, `/ludus-run`, `/ludus-runs`.

## Prerequisites

The backend and MCP server must be running and reachable:

```bash
docker compose up --build        # from the repo root: backend + mcp + frontend
```

The MCP server listens on port **8765** and proxies to the backend on **8000**.
If you run the MCP server on a different host/port, edit the `url` in `.mcp.json`.

## MCP tools exposed

`list_targets`, `list_scenarios`, `get_scenario`, `create_scenario`,
`run_scenario`, `list_runs`, `get_run`, `get_baseline`.
