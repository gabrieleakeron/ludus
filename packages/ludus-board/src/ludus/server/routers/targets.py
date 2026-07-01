"""Targets endpoints — list/declare targets known to the ludus core."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, select

from ludus.adapters import _REGISTRY
from ludus.server import service
from ludus.server.db import get_session
from ludus.server.db_models import TargetRow
from ludus.server.schemas import TargetCreate, TargetOut

router = APIRouter(prefix="/targets", tags=["targets"])


def _to_target_out(row: TargetRow) -> TargetOut:
    return TargetOut(
        key=row.key,
        kind=row.kind,
        description=row.description,
        requires_api_key=row.requires_api_key,
        runnable=row.key in _REGISTRY,
    )


@router.get("", response_model=list[TargetOut])
def list_targets(session: Session = Depends(get_session)) -> list[TargetOut]:
    """Return all registered targets (seeded from the adapter registry)."""
    service.seed_targets(session)
    rows = session.exec(select(TargetRow)).all()
    return [_to_target_out(row) for row in rows]


@router.post("", response_model=TargetOut)
def register_target(
    payload: TargetCreate, response: Response, session: Session = Depends(get_session)
) -> TargetOut:
    """Declare an authoring-only target (kind="declared").

    201 on create, 200 on idempotent re-declaration, 400 on an invalid key,
    409 if the key already exists as a runnable adapter.
    """
    try:
        row, created = service.register_target(
            session,
            key=payload.key,
            description=payload.description,
            requires_api_key=payload.requires_api_key,
        )
    except service.TargetConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except service.ServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response.status_code = 201 if created else 200
    return _to_target_out(row)


@router.get("/{key}", response_model=TargetOut)
def get_target(key: str, session: Session = Depends(get_session)) -> TargetOut:
    """Return a single target by key, including the computed `runnable` flag.

    404 if the key is neither a registry adapter nor a declared target.
    """
    service.seed_targets(session)
    row = session.get(TargetRow, key)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Target '{key}' not found.")
    return _to_target_out(row)
