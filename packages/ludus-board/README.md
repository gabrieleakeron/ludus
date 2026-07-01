# ludus-board

This package is **the app**: the Ludus AI eval framework and its alt-interface stack.
It is one of three packages in the `ludus` monorepo (see the
[repo-root README](../../README.md) for the overall layout) — this is the package you
develop against day to day.

## What's in here

- **Core eval framework** (`src/ludus/`) — the harness that runs a Target (a Claude Code
  agent, the Sethlans pipeline, a skill/prompt, or a model) against Scenarios and turns
  the results into scores, pass/fail gates, and regressions vs a baseline:
  `harness.py`, `adapters/`, `evaluators/`, `gate.py`, `baseline.py`, `cli.py`,
  `scenario.py`, `report.py`, `aggregate.py`, `models.py`.
- **Alt-interface backend** (`src/ludus/server/`) — a FastAPI + SQLModel/SQLite REST API
  (`ludus-server`) exposing scenarios, runs, and baselines over HTTP.
- **Alt-interface MCP server** (`src/ludus/mcp/`) — a thin MCP proxy (`ludus-mcp`) over
  the REST backend, so scenarios/runs/baselines can be driven from Claude.
- **Frontend** (`frontend/`) — a React/Vite/TypeScript SPA that consumes the REST API.
- **Docker** (`docker/`) — `backend.Dockerfile`, `mcp.Dockerfile`, `frontend.Dockerfile`,
  plus `docker-compose.yml` at this package's root to run all three together.
- `scenarios/`, `fixtures/`, `rubrics/` — scenario definitions and the assets they need.
- `tests/` — the pytest suite for the core and the alt-interface.

For the design/architecture background (vocabulary, layered design, the `RunResult`
contract) see the `ludus.wiki` repo, starting from `Home.md` → `Architecture.md`.

## Development

Requires **Python ≥ 3.11** and [uv](https://docs.astral.sh/uv/). Run these commands from
inside this directory (`packages/ludus-board/`):

```bash
# install (editable, with dev deps: pytest, ruff)
pip install -e ".[dev]"

# tests and lint
uv run pytest              # test suite (tests/, asyncio_mode=auto)
uv run ruff check .        # lint
uv run ruff format .       # format

# CLI (entry point "ludus" -> ludus.cli:main)
uv run ludus run scenarios/architect/breakdown-login.yaml --no-gate
uv run ludus baseline update scenarios/architect/breakdown-login.yaml
```

### Alt-interface stack

Optional extras `[server,mcp]` in `pyproject.toml`; entry points `ludus-server` ->
`ludus.server.main:run`, `ludus-mcp` -> `ludus.mcp.server:run`.

```bash
# full stack via Docker (see docker-compose.yml)
cp .env.example .env       # optional: set ANTHROPIC_API_KEY for live adapters
docker compose up --build  # frontend :8080, backend :8000 (/docs), mcp :8765/mcp

# local dev, no Docker
uv pip install -e ".[server,mcp]"
uv run uvicorn ludus.server.main:app --reload   # backend :8000
uv run ludus-mcp                                 # mcp :8765 (LUDUS_API_URL=http://localhost:8000)
cd frontend && npm install && npm run dev        # frontend :5173 (vite, proxies /api -> :8000)
cd frontend && npm run build                     # tsc -b && vite build
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).
