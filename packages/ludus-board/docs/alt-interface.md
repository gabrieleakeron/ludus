# Alt-Interface

An **alternative interface stack** on top of the CLI: a REST backend with SQLite
persistence, a web UI, an MCP server, and a Claude plugin. The core (`Harness`,
`Adapters`, `Evaluators`, `Gate`, `Baseline` — see the wiki's
[Architecture](../../../../ludus.wiki/Architecture.md)) is **not modified**; every
new layer reuses it as-is. This file is the source of truth; the published wiki
twin is `ludus.wiki/Alt-Interface.md` — keep the two in sync.

> **Status: initial scaffolding.** Every component has working stubs (the backend
> really executes an end-to-end mock run and persists it); the fuller build — richer
> UI, asynchronous execution, auth — is deferred to later iterations (see
> [Out of scope](#out-of-scope-next-iterations) below).
>
> **Packaging:** the code repo is now a `packages/` monorepo. Everything described
> in this doc (`src/ludus/server/`, `src/ludus/mcp/`, `frontend/`, `docker/`,
> `docker-compose.yml`) lives under `packages/ludus-board/` (this package). The
> Claude plugin has moved to the sibling package `packages/ludus-claude-plugin/`.
> End users no longer need any of this checked out — they get the stack via the
> `ludus` npm CLI (`ludus setup` + `ludus up`), which pulls prebuilt images from
> Docker Hub. See the wiki's Getting Started page ("Install (end users)") for that
> path; this doc describes the stack for **contributors** building it from source.

## Architecture

```
┌─────────────┐   HTTP    ┌──────────────┐   import   ┌───────────────┐
│ React SPA   │──────────▶│  Ludus BE    │───────────▶│  ludus core   │
│ (nginx)     │  REST     │  (FastAPI)   │  in-proc   │ Harness/…     │
└─────────────┘           │  + SQLModel  │            └───────────────┘
                          │  + SQLite    │
┌─────────────┐   HTTP    │  (volume)    │
│ Claude      │  (MCP)    └──────▲───────┘
│ plugin ─▶ MCP server ─────────┘  REST
└─────────────┘  (FastMCP streamable-http)
```

- **Backend** (`packages/ludus-board/src/ludus/server/`) — the single source of
  truth. Exposes REST, persists to SQLite via SQLModel, and executes runs by
  calling `Harness.run()` in-process (no separate worker/queue yet).
- **MCP** (`packages/ludus-board/src/ludus/mcp/`) — a thin layer; every tool is a
  proxy to a backend REST endpoint (via `httpx`). No eval logic is duplicated here.
- **Frontend** (`packages/ludus-board/frontend/`) — a React/Vite SPA served by
  nginx, consuming the REST API.
- **Plugin** (`packages/ludus-claude-plugin/`) — a Claude plugin manifest that
  registers the MCP server over HTTP and provides slash-commands. Bundled into
  the `packages/ludus` npm tarball at publish time for end-user installs.

### Repo layout

```
packages/ludus-board/
  src/ludus/server/   main.py, config.py, db.py, db_models.py, schemas.py,
                      service.py, routers/{health,targets,scenarios,runs,baselines}.py
  src/ludus/mcp/      server.py (FastMCP streamable-http), client.py (httpx → BE)
  frontend/           Vite+React+TS: src/api.ts, src/pages/{Targets,Scenarios,Runs,RunDetail}.tsx
                      src/components/DetailModal.tsx (shared read-only detail popup)
  docker/             backend.Dockerfile, mcp.Dockerfile, frontend.Dockerfile
  docker-compose.yml  LOCAL BUILD compose (contributor path), .env.example

packages/ludus-claude-plugin/
  .claude-plugin/plugin.json, .mcp.json, commands/*.md

packages/ludus/
  assets/docker-compose.yml   PULL-BASED compose (end-user path, `ludus up`)
```

## Data model (SQLite via SQLModel)

Maps the existing Pydantic models (`ludus.models`, `ludus.scenario`, `ludus.baseline`)
onto tables, using JSON blobs for the richer structures:

| Table | Key columns |
|---|---|
| `targets` | `key, kind, description, requires_api_key` — seeded from the adapter registry; `kind="declared"` for authoring-only targets registered via `POST /targets` |
| `scenarios` | `id, target, description, repeat, source_path, yaml_source, …` |
| `runs` | `id, scenario_id, target, n, status, overall_mean, pass_rate, gate_evaluated, gate_passed, report_text, created_at` — one record per N-repetition batch |
| `run_outcomes` | `id, run_id, idx, status, score, cost_usd, latency_ms, tokens_input, tokens_output, result_json, evaluations_json` |
| `baselines` | `scenario_id, target, overall_mean, pass_rate, n, timestamp, ludus_version` — mirrors `ludus.baseline.Baseline` |

Tables are created with `SQLModel.metadata.create_all` at startup — no Alembic yet.

## REST API

| Method | Path | Description |
|---|---|---|
| GET | `/health` | liveness + ludus version |
| GET | `/targets` | registered targets (seeded from the adapter registry) |
| POST | `/targets` | declare an authoring-only target (`kind="declared"`); 201 on create, 200 on idempotent re-declaration, 400 on invalid key, 409 if the key already names a runnable adapter |
| GET | `/targets/{key}` | target detail by key, including the computed `runnable` flag; 404 if unknown |
| GET | `/scenarios` | list scenarios |
| GET | `/scenarios/{id}` | scenario detail (+ YAML source) |
| POST | `/scenarios` | create a scenario from YAML |
| PUT | `/scenarios/{id}` | update an existing scenario's YAML in place (the YAML's `id` must match); 404 if the scenario does not exist yet |
| POST | `/runs` | execute a scenario N times and persist the result |
| GET | `/runs` | list runs (filter with `?scenario_id=`) |
| GET | `/runs/{id}` | run detail + per-repetition outcomes |
| GET | `/baselines/{scenario_id}` | stored baseline |

Live OpenAPI docs are served at `/docs` once the backend is running (`http://localhost:8000/docs`).

`TargetOut` (the shape returned by the `/targets` endpoints) carries a computed
**`runnable`** field: `true` iff the target's key is present in `ludus.adapters._REGISTRY`.
A target declared only via `POST /targets` (kind `"declared"`) is usable by scenarios
but `runnable=false` until a matching core adapter is implemented and registered.

## MCP tools

`list_targets`, `list_scenarios`, `get_scenario`, `create_scenario`, `update_scenario`,
`register_target`, `run_scenario`, `list_runs`, `get_run`, `get_baseline` — a 1:1
mapping onto the REST endpoints above.

## Running it

### End users: the `ludus` npm CLI (pull-based, recommended)

```bash
npm install -g https://github.com/gabrieleakeron/ludus/releases/latest/download/ludus-latest.tgz
ludus setup   # installs the Claude plugin into ~/.claude/plugins/ludus
ludus up      # pulls gabrieleconsonni/ludus-{server,board,mcp} from Docker Hub
```

This drives the pull-based compose in `packages/ludus/assets/docker-compose.yml`
(`image:` only, no `build:` block) — no checkout, no local build. `ludus down` /
`ludus status` are also available.

### Contributors: Docker (full stack, local build)

```bash
cd packages/ludus-board
cp .env.example .env      # optional: set ANTHROPIC_API_KEY to enable live adapters
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:8080 |
| Backend (OpenAPI at `/docs`) | http://localhost:8000 |
| MCP | http://localhost:8765/mcp |

Data (SQLite + baselines) survives restarts in the `ludus-data` Docker volume.

### Contributors: local dev (without Docker)

```bash
cd packages/ludus-board
uv pip install -e ".[server,mcp]"
uv run uvicorn ludus.server.main:app --reload        # backend :8000
uv run ludus-mcp                                      # MCP :8765 (LUDUS_API_URL=http://localhost:8000)
cd frontend && npm install && npm run dev             # SPA :5173 (proxies /api → :8000)
```

### Claude plugin

See `packages/ludus-claude-plugin/README.md`. With the stack running (either via
`ludus up` or the contributor compose), the `ludus` MCP server
(`http://localhost:8765/mcp`) shows as connected and the **`/ludus-create-scenario`**
command becomes available — it interactively creates or modifies a scenario
(registering/importing targets as needed) and pushes it to the backend. The
three old read-only commands (`/ludus-scenarios`, `/ludus-run`, `/ludus-runs`)
have been removed; browsing scenarios, targets and run history is now done in
the board SPA, and running a scenario from Claude Code is done directly via the
`run_scenario` MCP tool. End users get the plugin installed automatically by
`ludus setup`; contributors can point Claude Code at
`packages/ludus-claude-plugin/` directly.

### Board SPA detail popups

The Scenarios, Targets and Runs tables in the frontend each have an eye-icon
button per row that opens a read-only detail popup (a shared `DetailModal`
component, `frontend/src/components/DetailModal.tsx`) showing the full record —
e.g. a target's `runnable` flag and description, a scenario's YAML source, or a
run's per-repetition outcomes — without navigating away from the table.

## End-to-end verification

1. Core untouched: from `packages/ludus-board`, `uv run pytest` and `uv run ruff check .` stay green.
2. Backend: `GET /health` → 200; `GET /targets` includes `mock.architect`;
   `POST /runs {"scenario_id":"architetto-scomposizione-login","target":"mock.architect"}`
   → 201 with `overall_mean≈0.8`, `pass_rate=0.0`, 5 outcomes (keyless, via
   `MockAdapter`); data persists across a restart.
3. MCP: tools are listed and `run_scenario` produces the same result as the REST call.
4. Compose: the SPA lists targets/scenarios and can launch a mock run, showing results.

## Out of scope (next iterations)

- **Asynchronous** run execution with a queue and status polling (currently synchronous).
- Authentication / multi-tenancy on the backend.
- DB migrations (Alembic).
- Historical charts / richer regression views in the GUI.
- Move to PostgreSQL (isolated behind SQLModel, so this is a swap, not a rewrite).
