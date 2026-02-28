"""Workflow definitions."""

import datetime
import inspect
import json
import logging
from collections import defaultdict
from collections.abc import Callable, Iterable
from functools import wraps

import github
import rock
import snap
from models import CIRun, WorkflowSettings
from util import prepare_sandbox

logger = logging.getLogger(__name__)


WORKFLOWS = {}


def _register(labels: Iterable[str] = []):

    def decorator(f: Callable):
        global WORKFLOWS
        nonlocal labels
        _labels = [f.__qualname__, f.__qualname__.replace("_", "-"), *labels]
        for label in _labels:
            WORKFLOWS[label] = f

        @wraps(f)
        def wrapper(*args, **kwargs):
            return f(*args, **kwargs)

        return wrapper

    return decorator


def run(workflow: str, settings: WorkflowSettings) -> None:
    """Run a workflow with given settings.

    Args:
        workflow (str): workflow name/label.
        settings (WorkflowSettings): workflow settings.

    Raises:
        RuntimeError: if workflow is not defined.
    """
    if workflow not in WORKFLOWS:
        raise RuntimeError(f"Workflow {workflow} is not defined")

    WORKFLOWS[workflow](settings)


@_register(labels=["poke"])
def poke_ci(settings: WorkflowSettings):
    """Poke scheduled CI and re-run if failed and retries < 3."""
    repos = settings.repos
    retry_list: list[CIRun] = []
    for repo in repos:
        ci_run = github.get_last_scheduled_run(repo)
        if ci_run.should_retry:
            retry_list.append(ci_run)

        logger.info(f"{repo} - should retry: {ci_run.should_retry}")

    for _run in retry_list:
        github._post(repo, f"actions/runs/{_run.id}/rerun-failed-jobs")


@_register(labels=["heatmap"])
def generate_heatmap(settings: WorkflowSettings):
    """Generate heatmap of CI runs, plus general DevSecOps workflow information."""
    prepare_sandbox()
    repos = settings.repos
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

    github.push_changes(
        "kafka-ci",
        owner="imanenami",
        gh_user="iminions",
        gh_email="iman@datapy.co",
        add={"rawData.js": "js/rawData.js"},
    )


@_register(labels=["releases"])
def gather_releases(settings: WorkflowSettings):
    """..."""
    cfg = settings.config
    res = []
    # iterate over all defined charms
    for spec in cfg.values():
        subs = spec.substrate
        _main = snap.resolve_machine_charm_all if subs == "machine" else rock.resolve_k8s_charm_all
        versions = _main(spec)
        res.append((spec, versions))
        print(versions)

    # format results for a nice HTML/JS rendering:
    # final = {charm: {rel: {vm: ,k8s: } } }
    final = {}
    for spec, vers in res:
        subs = spec.substrate.replace("machine", "vm")
        canonical_name = spec.name.replace("-k8s", "")
        if canonical_name not in final:
            final[canonical_name] = defaultdict(lambda: {"vm": "---", "k8s": "---"})
        for ver in vers:
            snap_ver = f" ({ver.snap})" if ver.snap and ver.snap != "unknown" else ""
            ver_txt = ver.workload + snap_ver
            final[canonical_name][ver.charm][subs] = ver_txt

    formatted = {}
    for charm, data in final.items():
        formatted[charm] = [
            {"channel": c, "versions": {"k8s": data[c]["k8s"], "vm": data[c]["vm"]}} for c in data
        ]

    js = inspect.cleandoc(f"""
        updatedAt = "{datetime.datetime.now(tz=datetime.UTC).replace(microsecond=0)}";
        releaseData = {json.dumps(formatted)};
    """)

    print(js)
    with open("releaseData.js", "w") as f:
        f.write(js)
