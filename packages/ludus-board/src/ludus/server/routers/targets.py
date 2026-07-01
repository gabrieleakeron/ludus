"""Targets endpoints — list the adapters registered in the ludus core."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ludus.server.db import get_session
from ludus.server.db_models import TargetRow
from ludus.server.schemas import TargetOut
from ludus.server.service import seed_targets

router = APIRouter(prefix="/targets", tags=["targets"])


@router.get("", response_model=list[TargetOut])
def list_targets(session: Session = Depends(get_session)) -> list[TargetRow]:
    """Return all registered targets (seeded from the adapter registry)."""
    seed_targets(session)
    return list(session.exec(select(TargetRow)).all())
