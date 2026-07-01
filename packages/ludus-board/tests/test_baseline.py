"""Unit tests for baseline.py — IO round-trip, missing/malformed handling (AC5)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ludus.baseline import Baseline, baseline_path, build_baseline, load_baseline, save_baseline

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_baseline(scenario_id: str = "test-scenario") -> Baseline:
    return Baseline(
        scenario_id=scenario_id,
        target="mock.architect",
        overall_mean=0.85,
        pass_rate=0.8,
        n=5,
        timestamp="2026-06-30T12:00:00+00:00",
        ludus_version="0.1.0",
    )


# ---------------------------------------------------------------------------
# baseline_path
# ---------------------------------------------------------------------------


def test_baseline_path_returns_correct_file(tmp_path: Path) -> None:
    p = baseline_path("my-scenario", tmp_path)
    assert p == tmp_path / "my-scenario.json"


# ---------------------------------------------------------------------------
# save_baseline + load_baseline round-trip (AC5)
# ---------------------------------------------------------------------------


def test_baseline_round_trip(tmp_path: Path) -> None:
    """save then load returns the same required fields (AC5)."""
    bl = _make_baseline()
    save_baseline(bl, tmp_path)
    loaded = load_baseline("test-scenario", tmp_path)
    assert loaded is not None
    assert loaded.scenario_id == "test-scenario"
    assert loaded.overall_mean == pytest.approx(0.85)
    assert loaded.pass_rate == pytest.approx(0.8)
    assert loaded.n == 5
    assert loaded.timestamp == "2026-06-30T12:00:00+00:00"
    assert loaded.ludus_version == "0.1.0"
    assert loaded.target == "mock.architect"


def test_baseline_overwrite_is_idempotent(tmp_path: Path) -> None:
    """Re-writing the baseline overwrites the previous entry (idempotent per scenario_id)."""
    bl1 = _make_baseline()
    save_baseline(bl1, tmp_path)

    bl2 = Baseline(
        scenario_id="test-scenario",
        overall_mean=0.95,
        pass_rate=1.0,
        n=10,
        timestamp="2026-07-01T00:00:00+00:00",
        ludus_version="0.1.0",
    )
    save_baseline(bl2, tmp_path)

    loaded = load_baseline("test-scenario", tmp_path)
    assert loaded is not None
    assert loaded.overall_mean == pytest.approx(0.95)
    assert loaded.n == 10


def test_baseline_creates_directory(tmp_path: Path) -> None:
    """save_baseline creates the baselines directory if it does not exist."""
    nested = tmp_path / "deep" / "nested"
    bl = _make_baseline()
    save_baseline(bl, nested)
    assert (nested / "test-scenario.json").exists()


def test_baseline_save_returns_path(tmp_path: Path) -> None:
    """save_baseline returns the path to the written JSON file."""
    bl = _make_baseline()
    written = save_baseline(bl, tmp_path)
    assert written == tmp_path / "test-scenario.json"
    assert written.exists()


# ---------------------------------------------------------------------------
# load_baseline edge cases (AC5)
# ---------------------------------------------------------------------------


def test_load_baseline_missing_file_returns_none(tmp_path: Path) -> None:
    """Missing file => None, no exception (AC5)."""
    result = load_baseline("nonexistent-scenario", tmp_path)
    assert result is None


def test_load_baseline_garbage_json_returns_none(tmp_path: Path) -> None:
    """Malformed JSON => None, no exception (AC5)."""
    (tmp_path / "bad-scenario.json").write_text("not valid json {{{", encoding="utf-8")
    result = load_baseline("bad-scenario", tmp_path)
    assert result is None


def test_load_baseline_invalid_schema_returns_none(tmp_path: Path) -> None:
    """Valid JSON but wrong schema => None, no exception (AC5)."""
    bad = {"scenario_id": "test", "unexpected_field": 123}
    (tmp_path / "test.json").write_text(json.dumps(bad), encoding="utf-8")
    result = load_baseline("test", tmp_path)
    assert result is None


def test_load_baseline_empty_file_returns_none(tmp_path: Path) -> None:
    """Empty file => None, no exception."""
    (tmp_path / "empty.json").write_text("", encoding="utf-8")
    result = load_baseline("empty", tmp_path)
    assert result is None


# ---------------------------------------------------------------------------
# build_baseline helper
# ---------------------------------------------------------------------------


def test_build_baseline_sets_required_fields() -> None:
    """build_baseline populates all required fields including timestamp and version."""
    import ludus

    bl = build_baseline(
        scenario_id="my-scenario",
        target="mock.architect",
        overall_mean=0.75,
        pass_rate=0.6,
        n=3,
    )
    assert bl.scenario_id == "my-scenario"
    assert bl.overall_mean == pytest.approx(0.75)
    assert bl.pass_rate == pytest.approx(0.6)
    assert bl.n == 3
    assert bl.ludus_version == ludus.__version__
    assert bl.timestamp != ""
    assert "T" in bl.timestamp  # ISO-8601
