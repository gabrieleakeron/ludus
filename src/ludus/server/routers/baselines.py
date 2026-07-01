"""Baseline endpoints — read the stored regression baseline for a scenario."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ludus.server import service
from ludus.server.db import get_session
from ludus.server.schemas import BaselineOut

router = APIRouter(prefix="/baselines", tags=["baselines"])


@router.get("/{scenario_id}", response_model=BaselineOut)
def get_baseline(scenario_id: str, session: Session = Depends(get_session)):  # type: ignore[no-untyped-def]
    row = service.get_baseline_row(session, scenario_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No baseline for scenario '{scenario_id}'.")
    return row
