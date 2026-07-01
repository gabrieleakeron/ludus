# Ludus — Interfaccia alternativa alla CLI (BE + DB + GUI + MCP + Plugin)

Questo documento descrive la **struttura alternativa alla CLI** aggiunta a Ludus:
un backend dockerizzato con persistenza a DB ed esecuzione dei test, una GUI web,
un server MCP verso il backend e un plugin Claude. Il nucleo `ludus`
(harness/adapters/evaluators/gate/baseline) **non è stato modificato**: i nuovi
strati lo riusano integralmente.

> Stato: **scaffolding iniziale**. Ogni componente ha stub funzionanti (il backend
> esegue davvero una run mock end-to-end e la persiste); l'implementazione completa
> — code UI più ricca, esecuzione asincrona, auth — è demandata alle iterazioni
> successive (vedi "Fuori scope").

## Architettura

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

- **Backend** (`src/ludus/server/`): unica fonte di verità. Espone REST, persiste
  su SQLite (SQLModel) ed esegue le run richiamando `Harness.run()` in-process.
- **MCP** (`src/ludus/mcp/`): strato sottile; ogni tool è un proxy verso un
  endpoint REST del backend (`httpx`). Nessuna logica di eval duplicata.
- **Frontend** (`frontend/`): SPA React/Vite servita da nginx, consuma la REST.
- **Plugin** (`plugin/`): manifest Claude che registra il server MCP HTTP e
  fornisce slash-command.

## Struttura

```
src/ludus/server/   main.py, config.py, db.py, db_models.py, schemas.py,
                    service.py, routers/{health,targets,scenarios,runs,baselines}.py
src/ludus/mcp/      server.py (FastMCP streamable-http), client.py (httpx → BE)
frontend/           Vite+React+TS: src/api.ts, src/pages/{Targets,Scenarios,Runs,RunDetail}.tsx
plugin/             .claude-plugin/plugin.json, .mcp.json, commands/*.md
docker/             backend.Dockerfile, mcp.Dockerfile, frontend.Dockerfile
docker-compose.yml, .env.example
```

## Modello dati (SQLite via SQLModel)

Mappa i modelli Pydantic esistenti (`ludus.models`, `ludus.scenario`,
`ludus.baseline`) su tabelle, con blob JSON per le strutture ricche:

- `targets(key, kind, description, requires_api_key)` — seed dal registry adapter.
- `scenarios(id, target, description, repeat, source_path, yaml_source, …)`.
- `runs(id, scenario_id, target, n, status, overall_mean, pass_rate,
  gate_evaluated, gate_passed, report_text, created_at)` — un record per batch di N.
- `run_outcomes(id, run_id, idx, status, score, cost_usd, latency_ms,
  tokens_input, tokens_output, result_json, evaluations_json)`.
- `baselines(scenario_id, target, overall_mean, pass_rate, n, timestamp,
  ludus_version)` — allineata a `ludus.baseline.Baseline`.

Tabelle create con `SQLModel.metadata.create_all` allo startup (no Alembic per ora).

## API REST

| Metodo | Path | Descrizione |
|---|---|---|
| GET | `/health` | liveness + versione ludus |
| GET | `/targets` | target registrati (seed dal registry) |
| GET | `/scenarios` | elenco scenari |
| GET | `/scenarios/{id}` | dettaglio scenario (+ YAML) |
| POST | `/scenarios` | crea/aggiorna scenario da YAML |
| POST | `/runs` | esegue uno scenario N volte e persiste |
| GET | `/runs` | elenco run (filtro `?scenario_id=`) |
| GET | `/runs/{id}` | dettaglio run + outcome per ripetizione |
| GET | `/baselines/{scenario_id}` | baseline salvata |

## Tool MCP

`list_targets`, `list_scenarios`, `get_scenario`, `create_scenario`,
`run_scenario`, `list_runs`, `get_run`, `get_baseline` — 1:1 sugli endpoint REST.

## Come si avvia

### Docker (tutto lo stack)

```bash
cp .env.example .env      # opzionale: imposta ANTHROPIC_API_KEY per adapter live
docker compose up --build
# Frontend:  http://localhost:8080
# Backend:   http://localhost:8000  (OpenAPI: /docs)
# MCP:       http://localhost:8765/mcp
```

I dati (SQLite + baseline) sopravvivono ai restart nel volume `ludus-data`.

### Sviluppo locale (senza Docker)

```bash
uv pip install -e ".[server,mcp]"
uv run uvicorn ludus.server.main:app --reload        # backend :8000
uv run ludus-mcp                                      # MCP :8765 (LUDUS_API_URL=http://localhost:8000)
cd frontend && npm install && npm run dev             # SPA :5173 (proxy /api → :8000)
```

### Plugin Claude

Vedi `plugin/README.md`. Con lo stack attivo, il server MCP `ludus`
(`http://localhost:8765/mcp`) risulta connesso e i comandi `/ludus-scenarios`,
`/ludus-run`, `/ludus-runs` sono disponibili.

## Verifica end-to-end

1. Core intatto: `uv run pytest`, `uv run ruff check .` verdi.
2. Backend: `GET /health` → 200; `GET /targets` include `mock.architect`;
   `POST /runs {"scenario_id":"architetto-scomposizione-login","target":"mock.architect"}`
   → 201 con `overall_mean≈0.8`, `pass_rate=0.0`, 5 outcome (keyless via MockAdapter);
   i dati persistono dopo restart.
3. MCP: i tool sono elencati e `run_scenario` produce lo stesso risultato della REST.
4. Compose: la SPA elenca target/scenari e lancia una run mock mostrando i risultati.

## Fuori scope (iterazioni successive)

- Esecuzione run **asincrona**/con coda e polling stato (ora sincrona).
- Autenticazione/multiutenza sul backend.
- Migrazioni DB (Alembic).
- Grafici storici/regressioni avanzate nella GUI.
- Passaggio a PostgreSQL (isolato dietro SQLModel).
