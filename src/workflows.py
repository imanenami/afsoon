"""Workflow definitions."""

import datetime
import inspect
import json
import logging
from collections import defaultdict
from collections.abc import Callable, Iterable
from functools import partial, wraps

import github
import rock
import snap
import trivy
import util
from models import CIRun, WorkflowSettings

logger = logging.getLogger(__name__)


WORKFLOWS = {}
RunResults = str | None
WorflowProto = Callable[[WorkflowSettings], RunResults]


def register(aliases: Iterable[str] = []):
    """Register a workflow handler function, with optional aliases."""

    def decorator(f: WorflowProto):
        global WORKFLOWS
        nonlocal aliases
        _aliases = [f.__qualname__, f.__qualname__.replace("_", "-"), *aliases]
        for alias in _aliases:
            WORKFLOWS[alias] = f

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


def run(workflow: str, settings: WorkflowSettings) -> RunResults:
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


def prettyprint() -> None:
    """Pretty print workflows and their docs to stdout."""
    alias_map = defaultdict(lambda: [])
    for label, func in WORKFLOWS.items():
        alias_map[func].append(label)

    for func, aliases in alias_map.items():
        aliases.sort()
        quoted = [f'"{alias}"' for alias in aliases]
        print(f"  - {', '.join(quoted)}:", func.__doc__)


@register(aliases=["poke"])
def poke_ci(settings: WorkflowSettings) -> RunResults:
    """Poke scheduled CI and retry if failed and no. of retries < 3."""
    repos = [
        github.strip_gh_link(spec.repo) for spec in settings.charms.values() if spec.is_healthy
    ]
    logger.info(f"healthy repos: {', '.join(repos)}")
    retry_list: list[tuple[str, CIRun]] = []
    for repo in repos:
        ci_run = github.get_last_scheduled_run(repo)
        if ci_run.should_retry:
            retry_list.append((repo, ci_run))

        logger.info(f"{repo} - should retry: {ci_run.should_retry}")

    if settings.dry_run:
        return f"github/rerun-failed-job: {','.join(repo for repo, _ in retry_list)}"

    for repo, _run in retry_list:
        github._post(repo, f"actions/runs/{_run.id}/rerun-failed-jobs")

    return None


@register(aliases=["heatmap"])
def generate_heatmap(settings: WorkflowSettings) -> RunResults:
    """Generate heatmap of CI runs, plus general DevSecOps workflow information."""
    repos = [
        github.strip_gh_link(spec.repo) for spec in settings.charms.values() if spec.is_healthy
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

    outfile = f"{settings.output_dir}/rawData.js"
    util.write(outfile, raw_data)

    if settings.dry_run:
        return outfile

    push_to_kafka_ci(add={"rawData.js": "js/rawData.js"})
    return None


@register(aliases=["releases"])
def gather_releases(settings: WorkflowSettings) -> RunResults:
    """Gather charm releases and associated workflow versions for different tracks."""
    util.prepare_sandbox()
    cfg = settings.charms
    res = []
    # iterate over all defined charms
    for spec in cfg.values():
        subs = spec.substrate
        _main = snap.resolve_machine_charm_all if subs == "machine" else rock.resolve_k8s_charm_all
        versions = _main(spec)
        res.append((spec, versions))
        logger.info(versions)

    # format results for a nice HTML/JS rendering:
    # final = {charm: {rel: {vm: ,k8s: } } }
    final = {}
    _known_versions = set()
    for spec, vers in res:
        subs = spec.substrate.replace("machine", "vm")
        canonical_name = spec.name.replace("-k8s", "")
        if canonical_name not in final:
            final[canonical_name] = defaultdict(lambda: {"vm": "---", "k8s": "---"})
        for ver in vers:
            snap_ver = f" ({ver.snap})" if ver.snap and ver.snap != "unknown" else ""
            ver_txt = ver.workload + snap_ver
            final[canonical_name][ver.charm][subs] = ver_txt
            # gather known version format
            if spec.substrate == "machine":
                _known_versions.add(f'"snap","{spec.snap}","{ver.snap}","{ver.workload}"')
            else:
                _known_versions.add(f'"rock","{spec.name}","{ver.image}","{ver.workload}"')

    print("###\n\n" + "\n".join(_known_versions) + "\n###\n\n")

    formatted = {}
    for charm, data in final.items():
        formatted[charm] = [
            {"channel": c, "versions": {"k8s": data[c]["k8s"], "vm": data[c]["vm"]}} for c in data
        ]

    js = inspect.cleandoc(f"""
        updatedAt = "{datetime.datetime.now(tz=datetime.UTC).replace(microsecond=0)}";
        releaseData = {json.dumps(formatted)};
    """)

    outfile = f"{settings.output_dir}/releaseData.js"
    util.write(outfile, js)

    if settings.dry_run:
        return outfile

    push_to_kafka_ci(add={"releaseData.js": "js/releaseData.js"})
    return None


@register(aliases=["scan"])
def trivy_scan(settings: WorkflowSettings) -> RunResults:
    """Build from source and run Trivy scan on the rocks defined in "ROCKS" file."""
    util.prepare_sandbox()
    # install Trivy snap on sandbox
    util.exec(f"lxc exec {util.SANDBOX_INST} -- snap install --classic trivy")
    repos = settings.rocks
    for repo in repos:
        util.exec(f"scripts/vuln-scan.sh {util.SANDBOX_INST} {' '.join(repo.split('@'))}")
    vuln_list = trivy.combine_results()
    now = datetime.datetime.now(tz=datetime.UTC).replace(microsecond=0)
    raw = inspect.cleandoc(f"""
        updatedAt = '{now}';
        rawVulnData = {json.dumps(vuln_list)};
    """)

    outfile = f"{settings.output_dir}/vulnData.js"
    util.write(outfile, raw)

    if settings.dry_run:
        return outfile

    push_to_kafka_ci(add={"vulnData.js": "js/vulnData.js"})
    return None
