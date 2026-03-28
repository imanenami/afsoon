"""Workflow definitions."""

import logging

import github
from models import CIRun, Repo, WorkflowSettings

from .base import configured, register

logger = logging.getLogger(__name__)


@register(aliases=["poke"])
def poke_ci(settings: WorkflowSettings) -> None:
    """Poke scheduled CI and retry if failed and no. of retries < 3."""
    repos = {
        Repo(url=spec.ref.url)
        for spec in settings.charms.values()
        if configured(spec.ref, ("all", "poke"))
    }

    retry_list: list[tuple[Repo, CIRun]] = []
    for repo in repos:
        ci_run = github.get_last_scheduled_run(repo)
        if ci_run.should_retry:
            retry_list.append((repo, ci_run))

        logger.info(f"{repo} - should retry: {ci_run.should_retry}")

    for repo, _run in retry_list:
        github._post(repo, f"actions/runs/{_run.id}/rerun-failed-jobs")
