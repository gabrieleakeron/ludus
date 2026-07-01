"""Ludus MCP server — exposes the backend over the Model Context Protocol.

A thin layer: every tool maps to a REST call on the Ludus backend (no eval logic
is duplicated here). Designed to run as its own container over streamable HTTP so
a Claude plugin can connect to it by URL.

Install with the optional extra:  pip install -e ".[mcp]"
Run with:                         python -m ludus.mcp.server  (or `ludus-mcp`)
"""
