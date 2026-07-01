"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

import ludus

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "ludus_version": ludus.__version__}
