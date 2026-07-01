"""Scenario endpoints — list, read, and create scenarios from YAML."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ludus.server import service
from ludus.server.db import get_session
from ludus.server.schemas import ScenarioCreate, ScenarioOut

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("", response_model=list[ScenarioOut])
def list_scenarios(session: Session = Depends(get_session)):  # type: ignore[no-untyped-def]
    return service.list_scenarios(session)


@router.get("/{scenario_id}", response_model=ScenarioOut)
def get_scenario(scenario_id: str, session: Session = Depends(get_session)):  # type: ignore[no-untyped-def]
    try:
        return service.get_scenario(session, scenario_id)
    except service.ServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("", response_model=ScenarioOut, status_code=201)
def create_scenario(payload: ScenarioCreate, session: Session = Depends(get_session)):  # type: ignore[no-untyped-def]
    try:
        return service.create_scenario(session, payload.yaml_source)
    except service.ServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
