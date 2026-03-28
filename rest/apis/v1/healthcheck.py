# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Healthcheck API routes."""

from fastapi import APIRouter, Request

from ...core.models import HealthResponse

router = APIRouter()


@router.get("/readiness")
async def readiness(_: Request) -> HealthResponse:
    """Readiness Probe."""
    return HealthResponse(status="ok")


@router.get("/liveness")
async def liveness(_: Request) -> HealthResponse:
    """Liveness Probe."""
    return HealthResponse(status="ok")
