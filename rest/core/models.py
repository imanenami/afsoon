# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Domain models definition module."""

from typing import Literal

from pydantic import BaseModel

HealthStatus = Literal["ok", "error"]


class HealthResponse(BaseModel):
    """Response model for health check APIs."""

    status: HealthStatus


class Issue(BaseModel):
    """Response model for issues/PR API."""

    created: str
    created_days: int
    updated: str
    updated_days: int
    repo: str
    draft: bool
    title: str
    user: str


class IssuesResponse(BaseModel):
    """Response model for issues/PR API."""

    data: list[Issue]
