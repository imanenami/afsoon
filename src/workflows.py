"""Workflow definitions."""

import datetime
import inspect
import json
import logging
import os
from collections import defaultdict
from collections.abc import Callable, Iterable
from functools import partial, wraps

import github
import rock
import snap
import trivy
from models import CIRun, WorkflowSettings
from util import prepare_sandbox, SANDBOX_INST

logger = logging.getLogger(__name__)


WORKFLOWS = {}


def _register(labels: Iterable[str] = []):

    def decorator(f: Callable[[WorkflowSettings], None]):
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


push_to_kafka_ci = partial(
    github.push_changes,
    "kafka-ci",
    owner="imanenami",
    gh_user="iminions",
    gh_email="iman@datapy.co",
)


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
def poke_ci(settings: WorkflowSettings) -> None:
    """Poke scheduled CI and re-run if failed and retries < 3."""
    repos = [
        github.strip_gh_link(spec.repo) for spec in settings.config.values() if spec.is_healthy
    ]
    logger.info(f"healthy repos: {', '.join(repos)}")
    retry_list: list[CIRun] = []
    for repo in repos:
        ci_run = github.get_last_scheduled_run(repo)
        if ci_run.should_retry:
            retry_list.append(ci_run)

        logger.info(f"{repo} - should retry: {ci_run.should_retry}")

    for _run in retry_list:
        github._post(repo, f"actions/runs/{_run.id}/rerun-failed-jobs")


@_register(labels=["heatmap"])
def generate_heatmap(settings: WorkflowSettings) -> None:
    """Generate heatmap of CI runs, plus general DevSecOps workflow information."""
    repos = [
        github.strip_gh_link(spec.repo) for spec in settings.config.values() if spec.is_healthy
    ]
    logger.info(f"healthy repos: {', '.join(repos)}")
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

    push_to_kafka_ci(add={"rawData.js": "js/rawData.js"})


@_register(labels=["releases"])
def gather_releases(settings: WorkflowSettings) -> None:
    """..."""
    prepare_sandbox()
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

    push_to_kafka_ci(add={"releaseData.js": "js/releaseData.js"})


@_register(labels=["scan"])
def trivy_scan(settings: WorkflowSettings) -> None:
    """Run Trivy scan."""
    prepare_sandbox()
    # install Trivy snap on sandbox
    os.system(f"lxc exec {SANDBOX_INST} -- snap install --classic trivy")
    repos = trivy.load_rocks()
    for repo in repos:
        os.system(f"scripts/vuln-scan.sh {SANDBOX_INST} {' '.join(repo.split('@'))}")
    vuln_list = trivy.combine_results()
    now = datetime.datetime.now(tz=datetime.UTC).replace(microsecond=0)
    raw = inspect.cleandoc(f"""
        updatedAt = '{now}';
        rawVulnData = {json.dumps(vuln_list)};
    """)

    with open("vulnData.js", "w") as f:
        f.write(raw)

    push_to_kafka_ci(add={"vulnData.js": "js/vulnData.js"})
