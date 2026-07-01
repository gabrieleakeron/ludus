# ludus

Installer CLI for **Ludus AI**. It installs the Ludus Claude plugin into your
local Claude Code setup and runs the Ludus board (backend + MCP server +
frontend) as Docker containers, pulling prebuilt images from Docker Hub — it
does not build anything locally.

## Prerequisites

- Node.js >= 22
- [Docker](https://docs.docker.com/get-docker/) with **Compose v2** (the
  `docker compose` plugin subcommand — not the legacy standalone
  `docker-compose` binary)

## Install

```bash
npm install -g https://github.com/gabrieleakeron/ludus/releases/latest/download/ludus-latest.tgz
ludus setup
ludus up
```

After `ludus setup`, open Claude Code and run **`/reload-plugins`** (or restart
it) so it picks up the newly installed plugin — its command (`/ludus-create-scenario`)
and MCP server load on the next session. Browsing existing scenarios, targets and
run history is done in the board SPA (`ludus up`, then http://localhost:8080);
running a scenario from Claude Code is done via the `run_scenario` MCP tool.

`npm install` runs a best-effort `postinstall` that already performs the
`setup` step (installing the Claude plugin). Running `ludus setup` again
afterwards is safe (idempotent) and useful if postinstall was skipped, e.g.
because you installed with `--ignore-scripts`.

## Commands

| Command | What it does |
|---|---|
| `ludus setup` | Copies the bundled Claude plugin into `~/.claude/skills/ludus` (a skills-directory plugin — Claude Code auto-loads it as `ludus@skills-dir`, no marketplace needed) |
| `ludus up` | `docker compose up -d` against the bundled pull-based compose — starts backend (`:8000`), MCP (`:8765`), frontend (`:8080`) |
| `ludus down` | Stops and removes the board's containers |
| `ludus status` | Shows the board's container status (`docker compose ps`) |
| `ludus --version` / `-v` | Prints the installed CLI version |
| `ludus --help` / `-h` | Prints usage |

`--version` and `--help` have no side effects and no external dependencies —
they work even without Docker installed.

## Where things come from

- The board images (`gabrieleconsonni/ludus-server`, `gabrieleconsonni/ludus-mcp`,
  `gabrieleconsonni/ludus-board`) are pulled from **Docker Hub**. `ludus up`
  never builds an image locally.
- The Claude plugin bundled inside this package comes from the sibling
  `packages/ludus-claude-plugin` in the [ludus](https://github.com/gabrieleakeron/ludus)
  monorepo, copied in at publish time (`prepack`) so the published tarball is
  self-contained.

## Uninstall / reset

```bash
ludus down                        # stop the containers
npm uninstall -g ludus            # remove the CLI
rm -rf ~/.claude/skills/ludus     # remove the installed plugin (optional)
```

## Contributing / local development

This package is part of the [ludus](https://github.com/gabrieleakeron/ludus)
monorepo. From a full checkout:

```bash
cd packages/ludus
node bin/ludus.js --help          # run the CLI without installing
npm pack                          # build the tarball (runs prepack, which
                                   # bundles ../ludus-claude-plugin into
                                   # assets/ludus-claude-plugin)
```

See `packages/ludus-board/` for the actual Ludus eval framework (the app
these images are built from) and its own dev-oriented `docker-compose.yml`
(builds locally, for contributors).
