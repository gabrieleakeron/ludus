"""FastAPI application entry point for the Ludus backend.

Run in dev:   uvicorn ludus.server.main:app --reload
Console:      ludus-server
Docker:       see docker/backend.Dockerfile
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from ludus.server.config import get_settings
from ludus.server.db import create_db_and_tables, engine
from ludus.server.routers import baselines, fixtures, health, runs, scenarios, targets
from ludus.server.service import seed_scenarios, seed_targets


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Create tables and seed targets/scenarios on startup."""
    create_db_and_tables()
    get_settings().ensure_dirs()
    with Session(engine) as session:
        seed_targets(session)
        seed_scenarios(session)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Ludus API",
        description="Backend REST API over the Ludus eval core.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(targets.router)
    app.include_router(scenarios.router)
    app.include_router(fixtures.router)
    app.include_router(runs.router)
    app.include_router(baselines.router)
    return app


app = create_app()


def run() -> None:
    """Console-script entry point (`ludus-server`)."""
    import os

    import uvicorn

    uvicorn.run(
        "ludus.server.main:app",
        host=os.environ.get("LUDUS_HOST", "0.0.0.0"),
        port=int(os.environ.get("LUDUS_PORT", "8000")),
        reload=bool(os.environ.get("LUDUS_RELOAD", "")),
    )


if __name__ == "__main__":
    run()
