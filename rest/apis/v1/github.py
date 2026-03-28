# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""API routes definition."""

import json
import os
import subprocess
import time
from typing import Literal

from fastapi import APIRouter

from ...core.models import Issue, IssuesResponse

router = APIRouter()
MOD_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = MOD_DIR.split("/rest")[0]


def _exec(cmd, cwd: str | None = BASE_DIR) -> str:
    return subprocess.check_output(
        cmd,
        shell=True,
        universal_newlines=True,
        stderr=subprocess.PIPE,
        cwd=cwd,
    )


def _get_issues_service(
    type_: Literal["pr", "issue"], group: str = "kafka", expiry_seconds: int = 300
) -> list[Issue]:
    """Service to fetch open issues/PR.

    This service either uses a file cache, or calls the appropriate workflow.
    """
    out = f"{MOD_DIR}/{type_}_{group}.json"

    use_cache = False
    if os.path.exists(out) and time.time() - os.stat(out).st_mtime < expiry_seconds:
        use_cache = True

    if not use_cache:
        cmd = f"tox -e workflow -- issues type={type_} group={group} out={out}"
        _exec(cmd)

    with open(out) as f:
        j = json.load(f)

    return [Issue(**i) for i in j]


@router.get("/prs")
async def get_prs(group: str = "kafka") -> IssuesResponse:
    """Get open PRs."""
    return IssuesResponse(data=_get_issues_service("pr", group=group))


@router.get("/issues")
async def get_issues(group: str = "kafka") -> IssuesResponse:
    """Get open Issues."""
    return IssuesResponse(data=_get_issues_service("issue", group=group))
