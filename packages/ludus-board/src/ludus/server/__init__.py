"""Ludus backend — FastAPI + SQLModel REST API over the ludus core.

This package is an *alternative interface* to the CLI. It reuses the core
(`ludus.harness`, `ludus.scenario`, `ludus.adapters`, ...) unchanged and adds:
  - persistence to SQLite (via SQLModel)
  - a REST API to list targets/scenarios, trigger runs and read results

Install with the optional extra:  pip install -e ".[server]"
Run with:                         uvicorn ludus.server.main:app  (or `ludus-server`)
"""
