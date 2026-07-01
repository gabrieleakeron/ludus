"""Service layer — the bridge between the ludus core and the DB.

All heavy lifting is delegated to the existing core; this module only orchestrates
and persists. No evaluation/aggregation logic is reimplemented here.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

import yaml
from sqlmodel import Session, select

from ludus.adapters import _REGISTRY
from ludus.aggregate import overall_mean as compute_overall_mean
from ludus.aggregate import per_run_scores
from ludus.baseline import build_baseline, load_baseline, save_baseline
from ludus.gate import compute_pass_rate, evaluate_gate
from ludus.harness import Harness
from ludus.report import Reporter
from ludus.scenario import ScenarioError, load_scenario
from ludus.server.config import get_settings
from ludus.server.db_models import (
    BaselineRow,
    RunOutcomeRow,
    RunRow,
    ScenarioRow,
    TargetRow,
    _utcnow,
)


class ServiceError(Exception):
    """Raised for user-facing service errors (mapped to HTTP 400/404)."""


class TargetConflictError(ServiceError):
    """Raised when declaring a target key that already exists as a runnable adapter."""


class ScenarioNotFoundError(ServiceError):
    """Raised when an operation requires an existing scenario that is missing."""


_TARGET_KEY_RE = re.compile(r"^[a-z0-9._-]+$")
_SCENARIO_ID_RE = re.compile(r"^[a-z0-9._-]+$")


# --------------------------------------------------------------------------
# Seeding
# --------------------------------------------------------------------------


def seed_targets(session: Session) -> None:
    """Populate the targets table from the adapter registry (idempotent).

    Declared (authoring-only) rows are never clobbered, except that a declared
    key which now appears in the registry is promoted to kind="adapter".
    """
    for key in sorted(_REGISTRY):
        row = session.get(TargetRow, key)
        if row is None:
            session.add(
                TargetRow(
                    key=key,
                    kind="adapter",
                    description=f"Adapter target '{key}'.",
                    # Convention: mock.* adapters run keyless; others need an API key.
                    requires_api_key=not key.startswith("mock."),
                )
            )
        elif row.kind == "declared":
            row.kind = "adapter"
    session.commit()


# --------------------------------------------------------------------------
# Targets
# --------------------------------------------------------------------------


def register_target(
    session: Session,
    *,
    key: str,
    description: str = "",
    requires_api_key: bool = True,
) -> tuple[TargetRow, bool]:
    """Declare an authoring-only target (kind="declared").

    Idempotent: re-declaring the same key updates description/requires_api_key
    and returns the existing row. Raises TargetConflictError if the key is
    already a runnable adapter (kind="adapter"); raises ServiceError if the
    key fails charset validation.

    Returns (row, created) so the router's 201-vs-200 decision has a single
    source of truth instead of re-querying the table before calling in
    (which could drift out of sync with the seed_targets() call below).
    """
    seed_targets(session)

    normalized = key.strip()
    if not normalized or not _TARGET_KEY_RE.fullmatch(normalized):
        raise ServiceError(f"Invalid target key '{key}': must be non-empty and match [a-z0-9._-]+.")

    row = session.get(TargetRow, normalized)
    if row is not None and row.kind == "adapter":
        raise TargetConflictError(
            f"Target '{normalized}' already exists as a runnable adapter; reference it directly."
        )

    created = row is None
    if row is None:
        row = TargetRow(key=normalized, kind="declared")
        session.add(row)

    row.description = description
    row.requires_api_key = requires_api_key
    session.commit()
    session.refresh(row)
    return row, created


def seed_scenarios(session: Session) -> None:
    """Scan the scenarios directory and upsert a row per valid YAML (idempotent)."""
    settings = get_settings()
    if not settings.scenarios_dir.exists():
        return
    for path in sorted(settings.scenarios_dir.rglob("*.yaml")):
        try:
            scenario = load_scenario(path)
        except ScenarioError:
            continue  # skip invalid files during seeding
        _upsert_scenario_row(
            session,
            scenario_id=scenario.id,
            target=scenario.target,
            description=scenario.description,
            repeat=scenario.repeat,
            source_path=str(path),
            yaml_source=path.read_text(encoding="utf-8"),
        )
    session.commit()


# --------------------------------------------------------------------------
# Scenarios
# --------------------------------------------------------------------------


def _upsert_scenario_row(
    session: Session,
    *,
    scenario_id: str,
    target: str,
    description: str,
    repeat: int,
    source_path: str | None,
    yaml_source: str | None,
) -> ScenarioRow:
    row = session.get(ScenarioRow, scenario_id)
    if row is None:
        row = ScenarioRow(id=scenario_id)
        session.add(row)
    row.target = target
    row.description = description
    row.repeat = repeat
    if source_path is not None:
        row.source_path = source_path
    if yaml_source is not None:
        row.yaml_source = yaml_source
    return row


def _parse_scenario_yaml(yaml_source: str) -> dict:
    """Parse+validate raw scenario YAML text; return the raw mapping.

    Raises ServiceError if the YAML is malformed, lacks an 'id' field, or the
    'id' fails the safe-charset check (mirrors _TARGET_KEY_RE — this is the
    single choke point for both create_scenario and update_scenario, so the
    filesystem-writing path in _write_and_upsert_scenario never sees an id
    that could escape scenarios_dir, e.g. "../evil" or "foo/bar").
    """
    try:
        raw = yaml.safe_load(yaml_source)
    except yaml.YAMLError as exc:
        raise ServiceError(f"Invalid YAML: {exc}") from exc
    if not isinstance(raw, dict) or "id" not in raw:
        raise ServiceError("Scenario YAML must be a mapping with an 'id' field.")
    scenario_id = raw["id"]
    if not isinstance(scenario_id, str) or not _SCENARIO_ID_RE.fullmatch(scenario_id):
        raise ServiceError(
            f"Invalid scenario id {scenario_id!r}: must be non-empty and match [a-z0-9._-]+."
        )
    return raw


def _write_and_upsert_scenario(session: Session, yaml_source: str, raw: dict) -> ScenarioRow:
    """Write validated scenario YAML to disk and upsert its DB row.

    Shared by create_scenario and update_scenario so the two paths cannot diverge.
    """
    settings = get_settings()
    settings.ensure_dirs()
    scenarios_dir = settings.scenarios_dir.resolve()
    dest = settings.scenarios_dir / f"{raw['id']}.yaml"
    resolved_dest = dest.resolve()
    if resolved_dest.parent != scenarios_dir:
        # Defense-in-depth: _parse_scenario_yaml already enforces a safe
        # charset on raw["id"], so this should be unreachable in practice.
        raise ServiceError(f"Invalid scenario id {raw['id']!r}: resolves outside scenarios_dir.")
    previous = dest.read_text(encoding="utf-8") if dest.exists() else None
    dest.write_text(yaml_source, encoding="utf-8")

    try:
        scenario = load_scenario(dest)
    except ScenarioError as exc:
        if previous is None:
            dest.unlink(missing_ok=True)
        else:
            dest.write_text(previous, encoding="utf-8")
        raise ServiceError(str(exc)) from exc

    row = _upsert_scenario_row(
        session,
        scenario_id=scenario.id,
        target=scenario.target,
        description=scenario.description,
        repeat=scenario.repeat,
        source_path=str(dest),
        yaml_source=yaml_source,
    )
    row.updated_at = _utcnow()
    session.commit()
    session.refresh(row)
    return row


def create_scenario(session: Session, yaml_source: str) -> ScenarioRow:
    """Validate raw scenario YAML, persist it to disk, and upsert the DB row.

    The YAML is written to ``<scenarios_dir>/<id>.yaml`` so that relative
    fixture/rubric paths keep resolving exactly as the CLI expects.
    """
    raw = _parse_scenario_yaml(yaml_source)
    return _write_and_upsert_scenario(session, yaml_source, raw)


def update_scenario(session: Session, scenario_id: str, yaml_source: str) -> ScenarioRow:
    """Update an existing scenario's YAML in place.

    Raises ServiceError (->400) on invalid YAML or a path/id mismatch, and
    ScenarioNotFoundError (->404) if the scenario does not already exist.
    Reuses the same disk-write + load_scenario validation as create_scenario.
    """
    raw = _parse_scenario_yaml(yaml_source)
    if raw["id"] != scenario_id:
        raise ServiceError(
            f"Scenario id in YAML ('{raw['id']}') does not match path id ('{scenario_id}')."
        )
    if session.get(ScenarioRow, scenario_id) is None:
        raise ScenarioNotFoundError(f"Scenario '{scenario_id}' not found; use POST to create.")
    return _write_and_upsert_scenario(session, yaml_source, raw)


def list_scenarios(session: Session) -> list[ScenarioRow]:
    return list(session.exec(select(ScenarioRow)).all())


def get_scenario(session: Session, scenario_id: str) -> ScenarioRow:
    row = session.get(ScenarioRow, scenario_id)
    if row is None:
        raise ServiceError(f"Scenario '{scenario_id}' not found.")
    return row


# --------------------------------------------------------------------------
# Runs
# --------------------------------------------------------------------------


def _load_scenario_for_row(row: ScenarioRow):  # type: ignore[no-untyped-def]
    """Load a core Scenario from a stored row (prefer on-disk source_path)."""
    if row.source_path and Path(row.source_path).exists():
        return load_scenario(row.source_path)
    if row.yaml_source:
        # Fallback: materialize to a temp file so relative paths still resolve.
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as fh:
            fh.write(row.yaml_source)
            tmp = fh.name
        return load_scenario(tmp)
    raise ServiceError(f"Scenario '{row.id}' has no source to run.")


def execute_run(
    session: Session,
    *,
    scenario_id: str,
    target: str | None = None,
    n: int | None = None,
    update_baseline: bool = False,
) -> RunRow:
    """Run a scenario N times, persist the batch + per-repetition outcomes.

    Reuses Harness.run() and the core aggregation/gate/baseline helpers verbatim.
    Execution is synchronous (see plan: async/queue is a follow-up).
    """
    row = get_scenario(session, scenario_id)
    try:
        scenario = _load_scenario_for_row(row)
    except ScenarioError as exc:
        raise ServiceError(str(exc)) from exc

    resolved_target = target or scenario.target
    reps = n if n is not None else scenario.repeat

    try:
        outcomes = Harness().run(target=resolved_target, scenario=scenario, n=reps)
    except KeyError as exc:
        raise ServiceError(f"Unknown target: {exc}") from exc
    except Exception as exc:
        raise ServiceError(f"Run failed: {exc}") from exc

    settings = get_settings()
    om = compute_overall_mean(outcomes)
    pr = compute_pass_rate(outcomes)
    existing_baseline = load_baseline(scenario.id, settings.baselines_dir)
    gate_result = evaluate_gate(scenario, outcomes, existing_baseline)
    report_text = Reporter().render(scenario=scenario, outcomes=outcomes)

    run = RunRow(
        scenario_id=scenario.id,
        target=resolved_target,
        n=reps,
        status="completed",
        overall_mean=om,
        pass_rate=pr,
        gate_evaluated=gate_result.evaluated,
        gate_passed=gate_result.passed if gate_result.evaluated else None,
        report_text=report_text,
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    scores = per_run_scores(outcomes)
    for idx, (outcome, score) in enumerate(zip(outcomes, scores, strict=True)):
        rr = outcome.run_result
        session.add(
            RunOutcomeRow(
                run_id=run.id,  # type: ignore[arg-type]
                idx=idx,
                status=rr.status,
                score=score,
                cost_usd=rr.trace.cost_usd,
                latency_ms=rr.trace.latency_ms,
                tokens_input=rr.trace.tokens.input,
                tokens_output=rr.trace.tokens.output,
                result_json=rr.model_dump(),
                evaluations_json=[e.model_dump() for e in outcome.evaluations],
            )
        )
    session.commit()

    if update_baseline:
        bl = build_baseline(
            scenario_id=scenario.id,
            target=resolved_target,
            overall_mean=om,
            pass_rate=pr,
            n=reps,
        )
        save_baseline(bl, settings.baselines_dir)
        _upsert_baseline_row(session, bl)
        session.commit()

    session.refresh(run)
    return run


def list_runs(session: Session, scenario_id: str | None = None) -> list[RunRow]:
    stmt = select(RunRow)
    if scenario_id:
        stmt = stmt.where(RunRow.scenario_id == scenario_id)
    return list(session.exec(stmt.order_by(RunRow.id.desc())).all())  # type: ignore[union-attr]


def get_run(session: Session, run_id: int) -> tuple[RunRow, list[RunOutcomeRow]]:
    run = session.get(RunRow, run_id)
    if run is None:
        raise ServiceError(f"Run {run_id} not found.")
    outcomes = list(
        session.exec(
            select(RunOutcomeRow).where(RunOutcomeRow.run_id == run_id).order_by(RunOutcomeRow.idx)  # type: ignore[arg-type]
        ).all()
    )
    return run, outcomes


# --------------------------------------------------------------------------
# Baselines
# --------------------------------------------------------------------------


def _upsert_baseline_row(session: Session, bl) -> BaselineRow:  # type: ignore[no-untyped-def]
    row = session.get(BaselineRow, bl.scenario_id)
    if row is None:
        row = BaselineRow(scenario_id=bl.scenario_id)
        session.add(row)
    row.target = bl.target
    row.overall_mean = bl.overall_mean
    row.pass_rate = bl.pass_rate
    row.n = bl.n
    row.timestamp = bl.timestamp
    row.ludus_version = bl.ludus_version
    return row


def get_baseline_row(session: Session, scenario_id: str) -> BaselineRow | None:
    """Return the stored baseline, falling back to the on-disk JSON if present."""
    row = session.get(BaselineRow, scenario_id)
    if row is not None:
        return row
    bl = load_baseline(scenario_id, get_settings().baselines_dir)
    if bl is None:
        return None
    row = _upsert_baseline_row(session, bl)
    session.commit()
    session.refresh(row)
    return row


__all__ = [
    "ScenarioNotFoundError",
    "ServiceError",
    "TargetConflictError",
    "create_scenario",
    "execute_run",
    "get_baseline_row",
    "get_run",
    "get_scenario",
    "list_runs",
    "list_scenarios",
    "register_target",
    "seed_scenarios",
    "seed_targets",
    "update_scenario",
]
