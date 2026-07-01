"""Service layer — the bridge between the ludus core and the DB.

All heavy lifting is delegated to the existing core; this module only orchestrates
and persists. No evaluation/aggregation logic is reimplemented here.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path, PureWindowsPath

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


class FixtureError(ServiceError):
    """Raised for path-safety / validation errors on fixture paths (-> HTTP 400)."""


class FixtureNotFoundError(ServiceError):
    """Raised when a fixture is neither on disk nor referenced by any scenario (-> HTTP 404)."""


class FixtureConflictError(ServiceError):
    """Raised when uploading to an existing path without overwrite=True (-> HTTP 409)."""


class FixtureTooLargeError(ServiceError):
    """Raised when an uploaded file exceeds UPLOAD_MAX_BYTES (-> HTTP 413)."""


class FixtureUnsupportedTypeError(ServiceError):
    """Raised when an uploaded file's extension is not in the whitelist (-> HTTP 415)."""


class FixtureInvalidRootError(ServiceError):
    """Raised when the `root` query/form param is not 'fixtures'|'rubrics' (-> HTTP 422)."""


_TARGET_KEY_RE = re.compile(r"^[a-z0-9._-]+$")
_SCENARIO_ID_RE = re.compile(r"^[a-z0-9._-]+$")

# --------------------------------------------------------------------------
# Fixtures — constants (see story s6886e332 `## API Contract`)
# --------------------------------------------------------------------------

PREVIEW_MAX_BYTES = 256 * 1024  # 256 KiB
UPLOAD_MAX_BYTES = 5 * 1024 * 1024  # 5 MiB

TEXT_EXTENSIONS = (".md", ".txt", ".json", ".yaml", ".yml", ".csv", ".log")
UPLOAD_EXTENSIONS = (*TEXT_EXTENSIONS, ".zip")

_FIXTURE_ROOTS = ("fixtures", "rubrics")
# Charset applied per path segment (mirrors _SCENARIO_ID_RE's discipline, but
# allows '/' as the segment separator since fixtures may live in subdirs).
_PATH_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")

_CONTENT_TYPE_BY_EXT = {
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".json": "application/json",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
    ".csv": "text/csv",
    ".log": "text/plain",
    ".zip": "application/zip",
}


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
    "PREVIEW_MAX_BYTES",
    "TEXT_EXTENSIONS",
    "UPLOAD_EXTENSIONS",
    "UPLOAD_MAX_BYTES",
    "FixtureConflictError",
    "FixtureError",
    "FixtureInvalidRootError",
    "FixtureNotFoundError",
    "FixtureTooLargeError",
    "FixtureUnsupportedTypeError",
    "ScenarioNotFoundError",
    "ServiceError",
    "TargetConflictError",
    "create_scenario",
    "execute_run",
    "get_baseline_row",
    "get_fixture_config",
    "get_fixture_content",
    "get_run",
    "get_scenario",
    "list_runs",
    "list_scenario_fixtures",
    "list_scenarios",
    "register_target",
    "save_uploaded_fixture",
    "seed_scenarios",
    "seed_targets",
    "update_scenario",
]


# --------------------------------------------------------------------------
# Fixtures — path-safety (AC7)
# --------------------------------------------------------------------------


def _fixture_root_dir(root: str) -> Path:
    """Resolve the 'fixtures'|'rubrics' root name to its configured directory.

    Raises FixtureInvalidRootError (->422) for any other value.
    """
    if root not in _FIXTURE_ROOTS:
        raise FixtureInvalidRootError(
            f"Invalid root {root!r}: must be one of {', '.join(_FIXTURE_ROOTS)}."
        )
    settings = get_settings()
    return settings.fixtures_dir if root == "fixtures" else settings.rubrics_dir


def _validate_relative_path(raw_path: str) -> str:
    """Validate a fixture-relative path's charset/shape; return it normalized.

    Mirrors the discipline already used for scenario ids in `_SCENARIO_ID_RE` /
    `_write_and_upsert_scenario`, extended to multi-segment relative paths:
      - non-empty, not absolute (POSIX or Windows/UNC), no drive letter
      - no backslashes (Windows-style separators rejected outright)
      - no '..' path-traversal segments, no empty segments
      - each segment matches [A-Za-z0-9._-]+

    Raises FixtureError (->400) on any violation. This is intentionally the
    single choke point called by every fixture-facing function below.
    """
    if not raw_path or not raw_path.strip():
        raise FixtureError("Fixture path must not be empty.")
    if "\\" in raw_path:
        raise FixtureError(f"Invalid fixture path {raw_path!r}: backslashes are not allowed.")
    if raw_path.startswith(("/", "~")):
        raise FixtureError(f"Invalid fixture path {raw_path!r}: absolute paths are not allowed.")
    # Windows drive-letter / UNC detection (PureWindowsPath treats "C:/x" and
    # "C:x" as having a drive even on POSIX, which plain Path() would not).
    if PureWindowsPath(raw_path).drive:
        raise FixtureError(f"Invalid fixture path {raw_path!r}: drive letters are not allowed.")
    segments = raw_path.split("/")
    for seg in segments:
        if seg in ("", ".", ".."):
            raise FixtureError(
                f"Invalid fixture path {raw_path!r}: '..' and empty segments are not allowed."
            )
        if not _PATH_SEGMENT_RE.fullmatch(seg):
            raise FixtureError(
                f"Invalid fixture path segment {seg!r} in {raw_path!r}: must match [A-Za-z0-9._-]+."
            )
    return "/".join(segments)


def _resolve_fixture_path(root: str, raw_path: str) -> tuple[Path, str]:
    """Validate + resolve a (root, path) pair to an absolute filesystem path.

    Returns (absolute_path, normalized_relative_path). Performs strict
    containment verification via `resolve()` (defense-in-depth against
    symlink escapes etc.), matching the pattern in
    `_write_and_upsert_scenario`.
    """
    root_dir = _fixture_root_dir(root)
    rel = _validate_relative_path(raw_path)
    root_resolved = root_dir.resolve()
    candidate = (root_dir / rel).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise FixtureError(
            f"Invalid fixture path {raw_path!r}: resolves outside the {root} directory."
        ) from exc
    return candidate, rel


def _guess_content_type(path: Path) -> str | None:
    return _CONTENT_TYPE_BY_EXT.get(path.suffix.lower())


def _is_text_extension(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTENSIONS


def _sniff_is_binary(path: Path) -> bool:
    """Best-effort binary detection: NUL byte in the first 8 KiB, or non-text extension."""
    if not _is_text_extension(path):
        return True
    try:
        with path.open("rb") as fh:
            chunk = fh.read(8192)
    except OSError:
        return True
    return b"\x00" in chunk


# --------------------------------------------------------------------------
# Fixtures — scenario resolution (AD4)
# --------------------------------------------------------------------------


def _relative_to_root(abs_path: Path, root: str) -> str | None:
    """Return abs_path's path relative to the given named root, or None if outside it."""
    root_dir = _fixture_root_dir(root).resolve()
    try:
        return abs_path.resolve().relative_to(root_dir).as_posix()
    except (ValueError, OSError):
        return None


def _classify_under_roots(abs_path: Path) -> tuple[str, str] | None:
    """Classify an absolute path as belonging to 'fixtures' or 'rubrics'; else None."""
    for root in _FIXTURE_ROOTS:
        rel = _relative_to_root(abs_path, root)
        if rel is not None:
            return root, rel
    return None


def _fixture_ref_from_abs_path(abs_path_str: str, *, role: str, scenario_id: str) -> dict | None:
    """Build a FixtureRef-shaped dict from an absolute path resolved by Scenario.

    Returns None if the path does not fall under either configured root (so it
    cannot be represented as a FixtureRef; such scenarios are out of scope for
    this feature — AD4 assumes fixtures/rubrics live under the configured roots).
    """
    abs_path = Path(abs_path_str)
    classified = _classify_under_roots(abs_path)
    if classified is None:
        return None
    root, rel = classified
    present = abs_path.is_file()
    return {
        "root": root,
        "path": rel,
        "role": role,
        "scenario_id": scenario_id,
        "present": present,
        "size_bytes": abs_path.stat().st_size if present else None,
        "is_binary": _sniff_is_binary(abs_path) if present else None,
        "content_type": _guess_content_type(abs_path),
    }


def list_scenario_fixtures(session: Session, scenario_id: str) -> list[dict]:
    """List every fixture a scenario references (AC1) — prompt/context/rubric.

    Raises ScenarioNotFoundError (->404) if the scenario is unknown.
    """
    row = session.get(ScenarioRow, scenario_id)
    if row is None:
        raise ScenarioNotFoundError(f"Scenario '{scenario_id}' not found.")
    try:
        scenario = _load_scenario_for_row(row)
    except ScenarioError as exc:
        raise ServiceError(str(exc)) from exc

    refs: list[dict] = []
    prompt_ref = _fixture_ref_from_abs_path(
        scenario.input.prompt_fixture, role="prompt_fixture", scenario_id=scenario.id
    )
    if prompt_ref is not None:
        refs.append(prompt_ref)
    for f in scenario.context.files:
        ref = _fixture_ref_from_abs_path(f, role="context_files", scenario_id=scenario.id)
        if ref is not None:
            refs.append(ref)
    for exp in scenario.expectations:
        if exp.rubric:
            ref = _fixture_ref_from_abs_path(exp.rubric, role="rubric", scenario_id=scenario.id)
            if ref is not None:
                refs.append(ref)
    return refs


def _find_used_by(session: Session, root: str, rel_path: str) -> list[dict]:
    """Scan all stored scenarios for references to (root, rel_path) — AC3."""
    used_by: list[dict] = []
    for row in list_scenarios(session):
        try:
            scenario = _load_scenario_for_row(row)
        except ScenarioError:
            continue  # skip scenarios that fail to (re)load; not this endpoint's concern
        candidates = [("prompt_fixture", scenario.input.prompt_fixture)]
        candidates += [("context_files", f) for f in scenario.context.files]
        candidates += [("rubric", exp.rubric) for exp in scenario.expectations if exp.rubric]
        for role, abs_path_str in candidates:
            classified = _classify_under_roots(Path(abs_path_str))
            if classified == (root, rel_path):
                used_by.append({"scenario_id": scenario.id, "role": role})
    return used_by


# --------------------------------------------------------------------------
# Fixtures — content preview (AD5)
# --------------------------------------------------------------------------


def get_fixture_content(session: Session, root: str, raw_path: str) -> dict:
    """Read a fixture's content for preview (AC2/AC3/AC8).

    A missing-but-referenced fixture still returns present=False with
    used_by populated (so the FE can render the "missing" state + CTA).
    Raises FixtureNotFoundError (->404) only when the path is neither on
    disk nor referenced by any scenario.
    """
    abs_path, rel = _resolve_fixture_path(root, raw_path)
    used_by = _find_used_by(session, root, rel)
    present = abs_path.is_file()

    if not present and not used_by:
        raise FixtureNotFoundError(f"Fixture '{root}/{rel}' not found.")

    if not present:
        return {
            "root": root,
            "path": rel,
            "present": False,
            "size_bytes": None,
            "is_binary": False,
            "truncated": False,
            "content": None,
            "content_type": _guess_content_type(abs_path),
            "used_by": used_by,
        }

    size = abs_path.stat().st_size
    is_binary = _sniff_is_binary(abs_path)
    truncated = size > PREVIEW_MAX_BYTES
    content: str | None = None
    if not is_binary and not truncated:
        content = abs_path.read_text(encoding="utf-8", errors="replace")

    return {
        "root": root,
        "path": rel,
        "present": True,
        "size_bytes": size,
        "is_binary": is_binary,
        "truncated": truncated,
        "content": content,
        "content_type": _guess_content_type(abs_path),
        "used_by": used_by,
    }


# --------------------------------------------------------------------------
# Fixtures — upload (AD5, AC4/AC5/AC6/AC7/AC8)
# --------------------------------------------------------------------------


def save_uploaded_fixture(
    root: str, raw_path: str, data: bytes, *, overwrite: bool = False
) -> dict:
    """Validate + atomically write an uploaded fixture (AC4/AC5/AC6/AC7).

    Raises (in check order): FixtureInvalidRootError (422), FixtureError (400,
    path-safety), FixtureUnsupportedTypeError (415), FixtureTooLargeError
    (413), FixtureConflictError (409, exists and overwrite=False).

    Writes atomically: a temp file in the same target directory, then
    `os.replace` into place, so a crash mid-write never leaves a partial
    fixture visible to concurrent readers or the harness.
    """
    abs_path, rel = _resolve_fixture_path(root, raw_path)

    if abs_path.suffix.lower() not in UPLOAD_EXTENSIONS:
        raise FixtureUnsupportedTypeError(
            f"Unsupported fixture extension {abs_path.suffix!r}: "
            f"allowed extensions are {', '.join(UPLOAD_EXTENSIONS)}."
        )
    if len(data) > UPLOAD_MAX_BYTES:
        raise FixtureTooLargeError(
            f"Fixture exceeds the maximum upload size of {UPLOAD_MAX_BYTES} bytes."
        )

    created = not abs_path.is_file()
    if not created and not overwrite:
        raise FixtureConflictError(
            f"Fixture '{root}/{rel}' already exists; pass overwrite=true to replace it."
        )

    # mkdir stays strictly inside the resolved root — abs_path was already
    # containment-checked by _resolve_fixture_path above.
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(dir=str(abs_path.parent), prefix=".upload-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp_name, abs_path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise

    return {
        "root": root,
        "path": rel,
        "size_bytes": len(data),
        "created": created,
    }


def get_fixture_config() -> dict:
    """Return fixture limits/whitelists so the FE can pre-validate client-side."""
    return {
        "roots": list(_FIXTURE_ROOTS),
        "preview_max_bytes": PREVIEW_MAX_BYTES,
        "upload_max_bytes": UPLOAD_MAX_BYTES,
        "text_extensions": list(TEXT_EXTENSIONS),
        "upload_extensions": list(UPLOAD_EXTENSIONS),
    }
