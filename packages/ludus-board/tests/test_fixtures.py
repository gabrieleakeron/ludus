"""Tests for the fixtures feature (story s6886e332 / task tcbec12d4).

Covers:
  - path-safety unit tests (service._resolve_fixture_path / _validate_relative_path):
    traversal, absolute paths, backslashes, drive letters, bad charset.
  - integration tests against the real FastAPI app + filesystem:
    GET /scenarios/{id}/fixtures, GET /fixtures/content, POST /fixtures,
    GET /fixtures/config, and the contract's error status codes
    (400/404/409/413/415/422).

Uses the same tmp_path + monkeypatch + reload pattern as test_server.py so
each test gets an isolated scenarios/fixtures/rubrics tree.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Fresh FastAPI app wired to an isolated SQLite DB + scenarios/fixtures/rubrics dirs."""
    monkeypatch.setenv("LUDUS_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("LUDUS_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("LUDUS_SCENARIOS_DIR", str(tmp_path / "scenarios"))
    monkeypatch.setenv("LUDUS_BASELINES_DIR", str(tmp_path / "baselines"))
    monkeypatch.setenv("LUDUS_FIXTURES_DIR", str(tmp_path / "fixtures"))
    monkeypatch.setenv("LUDUS_RUBRICS_DIR", str(tmp_path / "rubrics"))

    import ludus.server.config as config_mod

    config_mod.get_settings.cache_clear()

    import ludus.server.db as db_mod

    importlib.reload(db_mod)

    import ludus.server.main as main_mod

    importlib.reload(main_mod)

    with TestClient(main_mod.app) as test_client:
        yield test_client

    config_mod.get_settings.cache_clear()


def _write_scenario(
    client: TestClient,
    scenario_id: str,
    *,
    prompt_fixture: str = "../fixtures/stories/login.md",
    context_files: list[str] | None = None,
    rubric: str | None = "../rubrics/architect.md",
) -> None:
    """Create a scenario via POST /scenarios, mirroring breakdown-login.yaml.

    Goes through the real API (rather than writing the YAML file directly)
    so the DB row + on-disk file are created consistently with how
    `service.create_scenario` expects them — writing the file directly after
    the FastAPI lifespan's `seed_scenarios()` already ran would leave the DB
    unaware of it, since list_scenario_fixtures/used_by resolve scenarios
    from the DB row (source_path), not by re-scanning the directory.
    """
    expectations = [{"type": "contains", "any_of": ["FastAPI"]}]
    if rubric:
        expectations.append({"type": "llm_judge", "rubric": rubric, "pass_threshold": 0.5})
    data = {
        "id": scenario_id,
        "target": "mock.architect",
        "description": "test scenario",
        "repeat": 1,
        "input": {"prompt_fixture": prompt_fixture},
        "context": {"files": context_files or []},
        "expectations": expectations,
    }
    resp = client.post("/scenarios", json={"yaml_source": yaml.dump(data)})
    assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# Path-safety — unit tests
# ---------------------------------------------------------------------------


def test_validate_relative_path_rejects_traversal() -> None:
    from ludus.server import service

    with pytest.raises(service.FixtureError):
        service._validate_relative_path("../../etc/passwd")


def test_validate_relative_path_rejects_absolute() -> None:
    from ludus.server import service

    with pytest.raises(service.FixtureError):
        service._validate_relative_path("/etc/passwd")


def test_validate_relative_path_rejects_backslash() -> None:
    from ludus.server import service

    with pytest.raises(service.FixtureError):
        service._validate_relative_path("..\\..\\windows\\win.ini")


def test_validate_relative_path_rejects_drive_letter() -> None:
    from ludus.server import service

    with pytest.raises(service.FixtureError):
        service._validate_relative_path("C:/Windows/win.ini")


def test_validate_relative_path_rejects_bad_charset() -> None:
    from ludus.server import service

    with pytest.raises(service.FixtureError):
        service._validate_relative_path("stories/login;rm -rf.md")


def test_validate_relative_path_accepts_normal_relative_path() -> None:
    from ludus.server import service

    assert service._validate_relative_path("stories/login.md") == "stories/login.md"


def test_resolve_fixture_path_rejects_invalid_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LUDUS_REPO_ROOT", str(tmp_path))
    import ludus.server.config as config_mod

    config_mod.get_settings.cache_clear()
    from ludus.server import service

    with pytest.raises(service.FixtureInvalidRootError):
        service._resolve_fixture_path("not-a-root", "stories/login.md")
    config_mod.get_settings.cache_clear()


# ---------------------------------------------------------------------------
# GET /scenarios/{id}/fixtures — AC1
# ---------------------------------------------------------------------------


def test_list_scenario_fixtures_reports_present_and_missing(
    client: TestClient, tmp_path: Path
) -> None:
    (tmp_path / "fixtures" / "stories").mkdir(parents=True)
    login_path = tmp_path / "fixtures" / "stories" / "login.md"
    login_path.write_bytes(b"# Login\n")  # write bytes directly: exact size, no newline translation
    # rubric intentionally NOT created -> missing
    _write_scenario(client, "architetto-scomposizione-login")

    resp = client.get("/scenarios/architetto-scomposizione-login/fixtures")
    assert resp.status_code == 200, resp.text
    refs = resp.json()
    by_role = {r["role"]: r for r in refs}

    assert by_role["prompt_fixture"]["path"] == "stories/login.md"
    assert by_role["prompt_fixture"]["root"] == "fixtures"
    assert by_role["prompt_fixture"]["present"] is True
    assert by_role["prompt_fixture"]["size_bytes"] == login_path.stat().st_size

    assert by_role["rubric"]["path"] == "architect.md"
    assert by_role["rubric"]["root"] == "rubrics"
    assert by_role["rubric"]["present"] is False
    assert by_role["rubric"]["size_bytes"] is None


def test_list_scenario_fixtures_404_unknown_scenario(client: TestClient) -> None:
    resp = client.get("/scenarios/does-not-exist/fixtures")
    assert resp.status_code == 404
    assert "detail" in resp.json()


# ---------------------------------------------------------------------------
# GET /fixtures/content — AC2/AC3/AC8
# ---------------------------------------------------------------------------


def test_get_fixture_content_text(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "fixtures" / "stories").mkdir(parents=True)
    (tmp_path / "fixtures" / "stories" / "login.md").write_text("# Login\nbody", encoding="utf-8")
    _write_scenario(client, "architetto-scomposizione-login")

    resp = client.get("/fixtures/content", params={"root": "fixtures", "path": "stories/login.md"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["present"] is True
    assert body["content"] == "# Login\nbody"
    assert body["is_binary"] is False
    assert body["truncated"] is False
    assert any(u["scenario_id"] == "architetto-scomposizione-login" for u in body["used_by"])


def test_get_fixture_content_empty_file(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "fixtures" / "golden").mkdir(parents=True)
    (tmp_path / "fixtures" / "golden" / "empty.md").write_text("", encoding="utf-8")

    resp = client.get("/fixtures/content", params={"root": "fixtures", "path": "golden/empty.md"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["present"] is True
    assert body["content"] == ""
    assert body["size_bytes"] == 0


def test_get_fixture_content_missing_but_referenced_returns_200(
    client: TestClient, tmp_path: Path
) -> None:
    _write_scenario(client, "architetto-scomposizione-login")  # rubric not on disk

    resp = client.get("/fixtures/content", params={"root": "rubrics", "path": "architect.md"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["present"] is False
    assert body["content"] is None
    assert len(body["used_by"]) == 1
    assert body["used_by"][0]["scenario_id"] == "architetto-scomposizione-login"


def test_get_fixture_content_404_missing_and_unreferenced(client: TestClient) -> None:
    resp = client.get("/fixtures/content", params={"root": "fixtures", "path": "nope.md"})
    assert resp.status_code == 404
    assert "detail" in resp.json()


def test_get_fixture_content_422_invalid_root(client: TestClient) -> None:
    resp = client.get("/fixtures/content", params={"root": "bogus", "path": "x.md"})
    assert resp.status_code == 422
    assert "detail" in resp.json()


def test_get_fixture_content_400_path_traversal(client: TestClient) -> None:
    resp = client.get("/fixtures/content", params={"root": "fixtures", "path": "../../etc/passwd"})
    assert resp.status_code == 400
    assert "detail" in resp.json()


def test_get_fixture_content_binary_too_large(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "fixtures" / "golden").mkdir(parents=True)
    big = b"\x00" + b"a" * (300 * 1024)  # > 256 KiB and has a NUL byte
    (tmp_path / "fixtures" / "golden" / "sample.zip").write_bytes(big)

    resp = client.get("/fixtures/content", params={"root": "fixtures", "path": "golden/sample.zip"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["present"] is True
    assert body["is_binary"] is True
    assert body["content"] is None


# ---------------------------------------------------------------------------
# POST /fixtures — AC4/AC5/AC6/AC7/AC8
# ---------------------------------------------------------------------------


def test_upload_fixture_creates_new_201(client: TestClient, tmp_path: Path) -> None:
    resp = client.post(
        "/fixtures",
        data={"root": "fixtures", "path": "stories/signup.md", "overwrite": "false"},
        files={"file": ("signup.md", b"# Signup\n", "text/markdown")},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["created"] is True
    assert body["path"] == "stories/signup.md"
    written = tmp_path / "fixtures" / "stories" / "signup.md"
    assert written.is_file()
    assert written.read_bytes() == b"# Signup\n"


def test_upload_fixture_duplicate_without_overwrite_409(client: TestClient) -> None:
    files = {"file": ("signup.md", b"v1", "text/markdown")}
    data = {"root": "fixtures", "path": "stories/dup.md", "overwrite": "false"}
    first = client.post("/fixtures", data=data, files=files)
    assert first.status_code == 201

    second = client.post(
        "/fixtures", data=data, files={"file": ("signup.md", b"v2", "text/markdown")}
    )
    assert second.status_code == 409
    assert "detail" in second.json()


def test_upload_fixture_overwrite_true_replaces_200(client: TestClient, tmp_path: Path) -> None:
    data = {"root": "fixtures", "path": "stories/replace-me.md"}
    first = client.post(
        "/fixtures",
        data={**data, "overwrite": "false"},
        files={"file": ("f.md", b"v1", "text/markdown")},
    )
    assert first.status_code == 201

    second = client.post(
        "/fixtures",
        data={**data, "overwrite": "true"},
        files={"file": ("f.md", b"v2", "text/markdown")},
    )
    assert second.status_code == 200, second.text
    assert second.json()["created"] is False
    written = tmp_path / "fixtures" / "stories" / "replace-me.md"
    assert written.read_bytes() == b"v2"


def test_upload_fixture_413_too_large(client: TestClient) -> None:
    from ludus.server import service

    too_big = b"a" * (service.UPLOAD_MAX_BYTES + 1)
    resp = client.post(
        "/fixtures",
        data={"root": "fixtures", "path": "golden/huge.md", "overwrite": "false"},
        files={"file": ("huge.md", too_big, "text/markdown")},
    )
    assert resp.status_code == 413
    assert "detail" in resp.json()


def test_upload_fixture_415_unsupported_extension(client: TestClient) -> None:
    resp = client.post(
        "/fixtures",
        data={"root": "fixtures", "path": "golden/script.exe", "overwrite": "false"},
        files={"file": ("script.exe", b"MZ", "application/octet-stream")},
    )
    assert resp.status_code == 415
    assert "detail" in resp.json()


def test_upload_fixture_400_path_traversal(client: TestClient, tmp_path: Path) -> None:
    resp = client.post(
        "/fixtures",
        data={"root": "fixtures", "path": "../../etc/passwd", "overwrite": "false"},
        files={"file": ("passwd", b"root:x:0:0", "text/plain")},
    )
    assert resp.status_code == 400
    assert "detail" in resp.json()
    # Ensure nothing was written outside the fixtures root.
    assert not (tmp_path.parent.parent / "etc" / "passwd").exists()


def test_upload_fixture_400_absolute_path(client: TestClient) -> None:
    resp = client.post(
        "/fixtures",
        data={"root": "fixtures", "path": "/etc/passwd", "overwrite": "false"},
        files={"file": ("passwd", b"root:x:0:0", "text/plain")},
    )
    assert resp.status_code == 400
    assert "detail" in resp.json()


def test_upload_fixture_422_invalid_root(client: TestClient) -> None:
    resp = client.post(
        "/fixtures",
        data={"root": "bogus", "path": "x.md", "overwrite": "false"},
        files={"file": ("x.md", b"hi", "text/plain")},
    )
    assert resp.status_code == 422
    assert "detail" in resp.json()


def test_upload_fixture_to_rubrics_root(client: TestClient, tmp_path: Path) -> None:
    resp = client.post(
        "/fixtures",
        data={"root": "rubrics", "path": "architect.md", "overwrite": "false"},
        files={"file": ("architect.md", b"# Rubric\n", "text/markdown")},
    )
    assert resp.status_code == 201, resp.text
    assert (tmp_path / "rubrics" / "architect.md").is_file()


# ---------------------------------------------------------------------------
# GET /fixtures/config
# ---------------------------------------------------------------------------


def test_get_fixture_config(client: TestClient) -> None:
    resp = client.get("/fixtures/config")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body["roots"]) == {"fixtures", "rubrics"}
    assert body["preview_max_bytes"] == 256 * 1024
    assert body["upload_max_bytes"] == 5 * 1024 * 1024
    assert ".md" in body["text_extensions"]
    assert ".zip" in body["upload_extensions"]
