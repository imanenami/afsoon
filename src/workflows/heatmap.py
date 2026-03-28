"""Workflow definitions."""

import datetime
import inspect
import json
import logging

import github
from models import WorkflowSettings

from .base import configured, push_to_remote, register

logger = logging.getLogger(__name__)


@register(aliases=["heatmap"])
def generate_heatmap(settings: WorkflowSettings) -> None:
    """Generate heatmap of CI runs, plus general DevSecOps workflow information."""
    repos = {
        spec.ref for spec in settings.charms.values() if configured(spec.ref, ("all", "heatmap"))
    }
    logger.info(f"healthy repos: {', '.join(repo.name for repo in repos)}")
    github.clone_repos(repos)
    wf_state = github.get_repos_wf_state(repos)
    heatmap_data = github.collect_scheduled_ci_stats(repos, last_n_days=20)
    # copy retry factor (rf) from heatmap_data to wf_state
    for hd in heatmap_data:
        if matching := [wd for wd in wf_state if wd["repo"] == hd["repo"]]:
            matching[0]["rf"] = hd["rf"]
    now = datetime.datetime.now(tz=datetime.UTC).replace(microsecond=0)
    raw_data = inspect.cleandoc(f"""
        updatedAt = '{now}';
        rawChartData = {json.dumps(heatmap_data)};
        rawGridData = {json.dumps(wf_state)};
    """)

    print(raw_data)
    with open("rawData.js", "w") as f:
        f.write(raw_data)

    push_to_remote(add={"rawData.js": "js/rawData.js"})
