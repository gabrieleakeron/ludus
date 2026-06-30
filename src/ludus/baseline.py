"""Baseline persistence for M2 gates (AD-M2-1).

Stores a single-point summary of a scenario run so that future runs can detect
regressions.  One JSON file per scenario, keyed by scenario_id, under a
``baselines/`` directory in the repo root.

On-disk schema (v1):
    schema_version, scenario_id, target, overall_mean, pass_rate, n,
    timestamp (UTC ISO-8601), ludus_version.

Functions
---------
baseline_path(scenario_id, baselines_dir) -> Path
load_baseline(scenario_id, baselines_dir) -> Baseline | None
    Returns None if the file does not exist or is malformed — never crashes.
save_baseline(b, baselines_dir) -> Path
    Creates baselines_dir when absent; overwrites the existing file (idempotent).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ValidationError

import ludus

logger = logging.getLogger(__name__)

# Default directory: resolved from cwd at call time, not at import time.
# The CLI passes the real path in; tests pass tmp_path.
DEFAULT_BASELINES_DIR = Path("baselines")


class Baseline(BaseModel):
    """Persisted summary of one scenario evaluation run."""

    schema_version: int = 1
    scenario_id: str
    target: str | None = None
    overall_mean: float
    pass_rate: float
    n: int
    timestamp: str
    ludus_version: str


def baseline_path(scenario_id: str, baselines_dir: Path) -> Path:
    """Return the expected JSON path for ``scenario_id`` inside ``baselines_dir``.

    Args:
        scenario_id: Scenario identifier string.
        baselines_dir: Directory that holds all baseline JSON files.

    Returns:
        Path object pointing to ``<baselines_dir>/<scenario_id>.json``.
    """
    return baselines_dir / f"{scenario_id}.json"


def load_baseline(scenario_id: str, baselines_dir: Path) -> Baseline | None:
    """Load a persisted Baseline or return None if absent/malformed.

    Args:
        scenario_id: Scenario identifier string.
        baselines_dir: Directory that holds all baseline JSON files.

    Returns:
        A validated ``Baseline`` or ``None`` (missing file, JSON error, or
        validation failure are all treated as "no baseline" — never raises).
    """
    path = baseline_path(scenario_id, baselines_dir)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Baseline.model_validate(raw)
    except (json.JSONDecodeError, ValidationError, OSError) as exc:
        logger.warning("Could not load baseline from %s: %s — treating as absent.", path, exc)
        return None


def save_baseline(b: Baseline, baselines_dir: Path) -> Path:
    """Persist a Baseline to disk, creating the directory if necessary.

    Args:
        b: The ``Baseline`` instance to serialise.
        baselines_dir: Directory that holds all baseline JSON files.

    Returns:
        The path to the written JSON file.
    """
    baselines_dir.mkdir(parents=True, exist_ok=True)
    path = baseline_path(b.scenario_id, baselines_dir)
    path.write_text(b.model_dump_json(indent=2), encoding="utf-8")
    return path


def build_baseline(
    scenario_id: str,
    target: str | None,
    overall_mean: float,
    pass_rate: float,
    n: int,
) -> Baseline:
    """Construct a Baseline from the current run's aggregated numbers.

    Args:
        scenario_id: Scenario identifier string.
        target: Target string (recorded for traceability, not used for comparison).
        overall_mean: Mean of per-run aggregate scores.
        pass_rate: Fraction of runs where all evaluators passed.
        n: Number of repetitions.

    Returns:
        A ready-to-persist ``Baseline`` instance.
    """
    return Baseline(
        scenario_id=scenario_id,
        target=target,
        overall_mean=overall_mean,
        pass_rate=pass_rate,
        n=n,
        timestamp=datetime.now(UTC).isoformat(),
        ludus_version=ludus.__version__,
    )
