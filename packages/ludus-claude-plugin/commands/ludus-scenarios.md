---
description: List the scenarios and targets known to the Ludus backend.
---

Use the Ludus MCP tools to give the user an overview of what can be evaluated:

1. Call `list_targets` and summarise the available targets (note which are keyless
   vs. which require an API key).
2. Call `list_scenarios` and present a compact table: id, target, repeat count,
   description.

If a tool call fails, the backend or MCP server is probably not running — remind
the user to start them (`docker compose up`, or run the backend + MCP locally).
