"""Backend configuration, sourced from environment variables.

All paths default to sensible repo-relative locations so the API runs out of the
box in development; Docker overrides them via env vars (see docker-compose.yml).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

# Repo root = four parents up from this file (src/ludus/server/config.py).
_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings:
    """Runtime settings resolved from the environment (with dev defaults)."""

    def __init__(self) -> None:
        self.repo_root: Path = Path(os.environ.get("LUDUS_REPO_ROOT", str(_REPO_ROOT)))

        # SQLite database URL. Default: a file in the repo's data/ dir.
        default_db = self.repo_root / "data" / "ludus.db"
        self.database_url: str = os.environ.get("LUDUS_DATABASE_URL", f"sqlite:///{default_db}")

        # Where scenario YAML files live / are written.
        self.scenarios_dir: Path = Path(
            os.environ.get("LUDUS_SCENARIOS_DIR", str(self.repo_root / "scenarios"))
        )

        # Where baseline JSON files are stored (reuses the CLI convention).
        self.baselines_dir: Path = Path(
            os.environ.get("LUDUS_BASELINES_DIR", str(self.repo_root / "baselines"))
        )

        # CORS origins for the SPA (comma-separated). "*" allows any.
        self.cors_origins: list[str] = [
            o.strip() for o in os.environ.get("LUDUS_CORS_ORIGINS", "*").split(",") if o.strip()
        ]

    def ensure_dirs(self) -> None:
        """Create data/scenarios/baselines directories if missing."""
        for p in (self.scenarios_dir, self.baselines_dir):
            p.mkdir(parents=True, exist_ok=True)
        if self.database_url.startswith("sqlite:///"):
            db_path = Path(self.database_url.removeprefix("sqlite:///"))
            db_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
