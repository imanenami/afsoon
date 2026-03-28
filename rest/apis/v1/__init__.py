# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""API routes definition."""

from fastapi import APIRouter

from . import github, healthcheck

api_router = APIRouter()

api_router.include_router(healthcheck.router, prefix="/healthcheck", tags=["healthcheck"])
api_router.include_router(github.router, prefix="/github", tags=["GitHub"])
