"""Run endpoints — trigger executions and read their results."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ludus.server import service
from ludus.server.db import get_session
from ludus.server.schemas import (
    RunCreate,
    RunDetailOut,
    RunOutcomeOut,
    RunSummaryOut,
)

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunDetailOut, status_code=201)
def create_run(payload: RunCreate, session: Session = Depends(get_session)):  # type: ignore[no-untyped-def]
    """Execute a scenario synchronously and return the persisted run + outcomes."""
    try:
        run = service.execute_run(
            session,
            scenario_id=payload.scenario_id,
            target=payload.target,
            n=payload.n,
            update_baseline=payload.update_baseline,
        )
    except service.ServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _run, outcomes = service.get_run(session, run.id)  # type: ignore[arg-type]
    return _to_detail(run, outcomes)


@router.get("", response_model=list[RunSummaryOut])
def list_runs(scenario_id: str | None = None, session: Session = Depends(get_session)):  # type: ignore[no-untyped-def]
    return service.list_runs(session, scenario_id)


@router.get("/{run_id}", response_model=RunDetailOut)
def get_run(run_id: int, session: Session = Depends(get_session)):  # type: ignore[no-untyped-def]
    try:
        run, outcomes = service.get_run(session, run_id)
    except service.ServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_detail(run, outcomes)


def _to_detail(run, outcomes) -> RunDetailOut:  # type: ignore[no-untyped-def]
    return RunDetailOut(
        id=run.id,
        scenario_id=run.scenario_id,
        target=run.target,
        n=run.n,
        status=run.status,
        overall_mean=run.overall_mean,
        pass_rate=run.pass_rate,
        gate_evaluated=run.gate_evaluated,
        gate_passed=run.gate_passed,
        created_at=run.created_at,
        report_text=run.report_text,
        outcomes=[
            RunOutcomeOut(
                idx=o.idx,
                status=o.status,
                score=o.score,
                cost_usd=o.cost_usd,
                latency_ms=o.latency_ms,
                tokens_input=o.tokens_input,
                tokens_output=o.tokens_output,
                result_json=o.result_json,
                evaluations_json=o.evaluations_json,
            )
            for o in outcomes
        ],
    )
