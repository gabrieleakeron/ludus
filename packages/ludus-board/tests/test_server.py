"""API tests for the scenario-authoring backend additions.

Covers:
  - TargetOut.runnable computed at read time from ludus.adapters._REGISTRY.
  - POST /targets (declare a target): create / idempotent / 400 / 409.
  - PUT /scenarios/{id} (update): happy path / 404 missing / 400 mismatch+invalid.
  - seed_targets promotion of a declared row that becomes a registry adapter.

Each test gets a fresh SQLite DB + scenarios dir by pointing the env vars the
config module reads at a tmp_path and reloading the affected modules, since
ludus.server.db creates its engine at import time from cached settings.
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
    """Fresh FastAPI app wired to an isolated SQLite DB + scenarios dir."""
    monkeypatch.setenv("LUDUS_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("LUDUS_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("LUDUS_SCENARIOS_DIR", str(tmp_path / "scenarios"))
    monkeypatch.setenv("LUDUS_BASELINES_DIR", str(tmp_path / "baselines"))

    import ludus.server.config as config_mod

    config_mod.get_settings.cache_clear()

    import ludus.server.db as db_mod

    importlib.reload(db_mod)

    import ludus.server.main as main_mod

    importlib.reload(main_mod)

    with TestClient(main_mod.app) as test_client:
        yield test_client

    config_mod.get_settings.cache_clear()


def _scenario_yaml(scenario_id: str, target: str = "mock.architect") -> str:
    data = {
        "id": scenario_id,
        "target": target,
        "repeat": 1,
        "input": {"prompt_fixture": "fixtures/stories/login.md"},
        "expectations": [{"type": "contains", "any_of": ["FastAPI"]}],
    }
    return yaml.dump(data)


# ---------------------------------------------------------------------------
# TargetOut.runnable
# ---------------------------------------------------------------------------


def test_list_targets_runnable_true_for_registry_key(client: TestClient) -> None:
    resp = client.get("/targets")
    assert resp.status_code == 200
    by_key = {t["key"]: t for t in resp.json()}
    assert by_key["mock.architect"]["runnable"] is True
    assert by_key["mock.architect"]["kind"] == "adapter"


def test_list_targets_runnable_false_for_declared_key(client: TestClient) -> None:
    create_resp = client.post("/targets", json={"key": "custom.tool", "description": "d"})
    assert create_resp.status_code == 201
    assert create_resp.json()["runnable"] is False

    resp = client.get("/targets")
    by_key = {t["key"]: t for t in resp.json()}
    assert by_key["custom.tool"]["runnable"] is False
    assert by_key["custom.tool"]["kind"] == "declared"


# ---------------------------------------------------------------------------
# GET /targets/{key}
# ---------------------------------------------------------------------------


def test_get_target_runnable_true_for_registry_key(client: TestClient) -> None:
    resp = client.get("/targets/mock.architect")
    assert resp.status_code == 200
    body = resp.json()
    assert body["key"] == "mock.architect"
    assert body["kind"] == "adapter"
    assert body["runnable"] is True


def test_get_target_runnable_false_for_declared_key(client: TestClient) -> None:
    create_resp = client.post("/targets", json={"key": "custom.detail", "description": "d"})
    assert create_resp.status_code == 201

    resp = client.get("/targets/custom.detail")
    assert resp.status_code == 200
    body = resp.json()
    assert body["key"] == "custom.detail"
    assert body["kind"] == "declared"
    assert body["runnable"] is False


def test_get_target_missing_404(client: TestClient) -> None:
    resp = client.get("/targets/does-not-exist")
    assert resp.status_code == 404
    assert "detail" in resp.json()


# ---------------------------------------------------------------------------
# POST /targets
# ---------------------------------------------------------------------------


def test_register_target_creates_201(client: TestClient) -> None:
    resp = client.post(
        "/targets", json={"key": "my.declared-target-1", "description": "authoring only"}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["key"] == "my.declared-target-1"
    assert body["kind"] == "declared"
    assert body["runnable"] is False


def test_register_target_idempotent_200(client: TestClient) -> None:
    payload = {"key": "idempotent.tool", "description": "v1", "requires_api_key": True}
    first = client.post("/targets", json=payload)
    assert first.status_code == 201

    payload["description"] = "v2"
    second = client.post("/targets", json=payload)
    assert second.status_code == 200
    assert second.json()["description"] == "v2"


def test_register_target_invalid_key_400(client: TestClient) -> None:
    resp = client.post("/targets", json={"key": "Invalid Key!"})
    assert resp.status_code == 400
    assert "detail" in resp.json()


def test_register_target_empty_key_400(client: TestClient) -> None:
    resp = client.post("/targets", json={"key": "   "})
    assert resp.status_code == 400


def test_register_target_conflict_with_adapter_409(client: TestClient) -> None:
    resp = client.post("/targets", json={"key": "mock.architect"})
    assert resp.status_code == 409
    assert "detail" in resp.json()


# ---------------------------------------------------------------------------
# PUT /scenarios/{id}
# ---------------------------------------------------------------------------


def test_update_scenario_happy_path(client: TestClient) -> None:
    create_resp = client.post("/scenarios", json={"yaml_source": _scenario_yaml("upd-1")})
    assert create_resp.status_code == 201
    created_updated_at = create_resp.json()["updated_at"]

    new_yaml = _scenario_yaml("upd-1", target="mock.architect")
    new_yaml = new_yaml.replace("repeat: 1", "repeat: 2")
    update_resp = client.put("/scenarios/upd-1", json={"yaml_source": new_yaml})
    assert update_resp.status_code == 200, update_resp.text
    body = update_resp.json()
    assert body["repeat"] == 2
    assert body["updated_at"] >= created_updated_at


def test_update_scenario_missing_404(client: TestClient) -> None:
    resp = client.put(
        "/scenarios/does-not-exist", json={"yaml_source": _scenario_yaml("does-not-exist")}
    )
    assert resp.status_code == 404
    assert "detail" in resp.json()


def test_update_scenario_id_mismatch_400(client: TestClient) -> None:
    client.post("/scenarios", json={"yaml_source": _scenario_yaml("mismatch-1")})
    resp = client.put("/scenarios/mismatch-1", json={"yaml_source": _scenario_yaml("other-id")})
    assert resp.status_code == 400
    assert "detail" in resp.json()


def test_update_scenario_invalid_yaml_400(client: TestClient) -> None:
    client.post("/scenarios", json={"yaml_source": _scenario_yaml("bad-yaml-1")})
    resp = client.put("/scenarios/bad-yaml-1", json={"yaml_source": "not: [a, valid\nyaml"})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Path traversal via scenario id (BLOCKER B1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_id",
    [
        "../evil",
        "foo/bar",
        "..\\evil",
        "/etc/evil",
        "C:\\evil",
    ],
)
def test_create_scenario_rejects_unsafe_id(client: TestClient, tmp_path: Path, bad_id: str) -> None:
    resp = client.post("/scenarios", json={"yaml_source": _scenario_yaml(bad_id)})
    assert resp.status_code == 400, resp.text
    assert "detail" in resp.json()
    # Nothing must have been written outside (or even inside) scenarios_dir.
    assert not any(tmp_path.rglob("evil.yaml"))


@pytest.mark.parametrize(
    "bad_id",
    [
        "../evil",
        "foo/bar",
        "..\\evil",
        "/etc/evil",
        "C:\\evil",
    ],
)
def test_update_scenario_rejects_unsafe_id(client: TestClient, tmp_path: Path, bad_id: str) -> None:
    # PUT path segment mirrors the (unsafe) id so the id-match check passes
    # and the charset validation in _parse_scenario_yaml is what's exercised.
    resp = client.put(
        f"/scenarios/{bad_id}",
        json={"yaml_source": _scenario_yaml(bad_id)},
    )
    assert resp.status_code in (400, 404)
    assert "detail" in resp.json()
    assert not any(tmp_path.rglob("evil.yaml"))


def test_create_scenario_normal_id_still_works(client: TestClient) -> None:
    resp = client.post("/scenarios", json={"yaml_source": _scenario_yaml("normal-id-1")})
    assert resp.status_code == 201, resp.text
    assert resp.json()["id"] == "normal-id-1"


# ---------------------------------------------------------------------------
# seed_targets promotion
# ---------------------------------------------------------------------------


def test_seed_targets_promotes_declared_to_adapter(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlmodel import Session

    import ludus.adapters as adapters_mod
    from ludus.server.db import engine
    from ludus.server.db_models import TargetRow
    from ludus.server.service import seed_targets

    declare_resp = client.post("/targets", json={"key": "future.adapter"})
    assert declare_resp.status_code == 201

    monkeypatch.setitem(adapters_mod._REGISTRY, "future.adapter", lambda: None)
    try:
        with Session(engine) as session:
            seed_targets(session)
            row = session.get(TargetRow, "future.adapter")
            assert row is not None
            assert row.kind == "adapter"
    finally:
        adapters_mod._REGISTRY.pop("future.adapter", None)


def test_seed_targets_leaves_unrelated_declared_rows_untouched(client: TestClient) -> None:
    client.post("/targets", json={"key": "still.declared"})

    resp = client.get("/targets")
    by_key = {t["key"]: t for t in resp.json()}
    assert by_key["still.declared"]["kind"] == "declared"
    assert by_key["still.declared"]["runnable"] is False
