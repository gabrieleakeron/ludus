"""Fixture endpoints — list, preview, and upload/replace scenario fixtures.

Implements the contract in the story `s6886e332` `## API Contract` section:
  GET  /scenarios/{scenario_id}/fixtures
  GET  /fixtures/content?root=&path=
  POST /fixtures  (multipart, overwrite flag covers both create and replace)
  GET  /fixtures/config

All filesystem work is delegated to `ludus.server.service` (path-safety,
preview, atomic upload); this module only maps service exceptions to the
HTTP status codes from the contract (400/404/409/413/415/422), always as
`{"detail": "..."}`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlmodel import Session

from ludus.server import service
from ludus.server.db import get_session
from ludus.server.schemas import (
    FixtureConfigOut,
    FixtureContentOut,
    FixtureRefOut,
    FixtureUploadOut,
)

router = APIRouter(tags=["fixtures"])


def _service_error_to_http(exc: service.ServiceError) -> HTTPException:
    """Map a ServiceError subclass to the HTTP status code from the contract."""
    if isinstance(exc, service.ScenarioNotFoundError | service.FixtureNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, service.FixtureConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, service.FixtureTooLargeError):
        return HTTPException(status_code=413, detail=str(exc))
    if isinstance(exc, service.FixtureUnsupportedTypeError):
        return HTTPException(status_code=415, detail=str(exc))
    if isinstance(exc, service.FixtureInvalidRootError):
        return HTTPException(status_code=422, detail=str(exc))
    # FixtureError and any other ServiceError: path-safety / generic validation -> 400
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/scenarios/{scenario_id}/fixtures", response_model=list[FixtureRefOut])
def list_scenario_fixtures(  # type: ignore[no-untyped-def]
    scenario_id: str, session: Session = Depends(get_session)
):
    try:
        return service.list_scenario_fixtures(session, scenario_id)
    except service.ServiceError as exc:
        raise _service_error_to_http(exc) from exc


@router.get("/fixtures/content", response_model=FixtureContentOut)
def get_fixture_content(  # type: ignore[no-untyped-def]
    root: str = Query(...),
    path: str = Query(...),
    session: Session = Depends(get_session),
):
    try:
        return service.get_fixture_content(session, root, path)
    except service.ServiceError as exc:
        raise _service_error_to_http(exc) from exc


@router.post("/fixtures", response_model=FixtureUploadOut)
async def upload_fixture(  # type: ignore[no-untyped-def]
    response: Response,
    root: str = Form(...),
    path: str = Form(...),
    overwrite: bool = Form(False),
    file: UploadFile = File(...),  # noqa: B008 - FastAPI's required DI idiom, not a real mutable-default risk
):
    data = await file.read()
    try:
        result = service.save_uploaded_fixture(root, path, data, overwrite=overwrite)
    except service.ServiceError as exc:
        raise _service_error_to_http(exc) from exc
    # 201 for a brand-new file, 200 when an existing one was overwritten
    # (contract: POST /fixtures dual-purposes as create+replace via `overwrite`).
    response.status_code = 201 if result["created"] else 200
    return FixtureUploadOut(**result)


@router.get("/fixtures/config", response_model=FixtureConfigOut)
def get_fixture_config():  # type: ignore[no-untyped-def]
    return service.get_fixture_config()
