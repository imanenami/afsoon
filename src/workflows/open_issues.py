"""Workflow definitions."""

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial

import github
from models import WorkflowSettings
from util import keep_main_only

from .base import register

logger = logging.getLogger(__name__)


@register(aliases=["issues"])
# params: group, type, out
def open_issues(settings: WorkflowSettings):
    """Get open PRs or Issues.

    Accepted workflow params are:
        out (required): output file path,
        type: "pr" or "issue",
        group: charm engineering group.
    """
    outfile = settings.params.get("out")
    if not outfile:
        raise RuntimeError("open_issues requires 'out' param to be defined.")

    # ignore branch for this.
    repos = [
        repo
        for repo in keep_main_only(settings.repos)
        if repo.group == settings.params.get("group", "kafka")
    ]
    results = {}
    func = partial(github.get_open_issues, results, type_=settings.params.get("type", "pr"))
    with ThreadPoolExecutor(max_workers=8) as tpe:
        _ = tpe.map(func, repos)
        tpe.shutdown(wait=True)

    data = [i for v in results.values() for i in v]
    with open(outfile, "w") as f:
        json.dump(data, f)
