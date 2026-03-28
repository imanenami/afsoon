"""GitHub helpers module."""

import datetime
import glob
import logging
import os
import re
import shutil
import tempfile
from collections import defaultdict
from collections.abc import Iterable
from functools import partial
from typing import Any, Literal
from urllib.parse import urlencode

import requests
import yaml
from git import Repo as GitRepo

from models import CIRun, Repo
from util import TMP_PREFIX, dtdiff, exec, get_or_create_tmp_path

logger = logging.getLogger("GitHub")

TMP_PATH = get_or_create_tmp_path()

OWNER = "canonical"
TOKEN = os.environ.get("CI_TOKEN", "NOT_DEFINED").replace('"', "").replace("'", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "NOT_DEFINED").replace('"', "").replace("'", "")

GH_API_VERSION = "2022-11-28"
BASE_URI = "https://api.github.com/repos"

IN_PROGRESS = "in_progress"
COMPLETED = "completed"

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "X-GitHub-Api-Version": GH_API_VERSION,
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _req(method: Literal["POST", "GET"], repo: Repo, api: str, **kwargs: Any):
    api_url = f"{BASE_URI}/{repo.owner}/{repo.short_name}/{api}"
    logger.debug(f"req url: {api_url}")
    match method:
        case "GET":
            resp = requests.get(api_url, headers=HEADERS)
        case "POST":
            resp = requests.post(api_url, headers=HEADERS)

    if resp.status_code // 100 != 2:
        raise Exception(f"GH request failed: {resp.text}")

    return resp.json()


_get = partial(_req, "GET")
_post = partial(_req, "POST")


def _format_workflow_name(wf: str) -> str:
    return wf.replace("canonical/data-platform-workflows/.github/workflows", "DPW")


def _format_test_stats(stats: dict) -> str:
    """Format test stats as a renderable string."""
    total = sum(stats.values())
    if total == 0:
        return "0:100"
    n_jub = stats["jubilant"]
    g = int(100 * n_jub / total)
    r = 100 - g
    return f"{g}:{r}"


def clone_repos(repos: Iterable[Repo], owner=OWNER) -> None:
    """Clone an iterable of GitHub repos."""
    for repo in repos:
        os.system(f"git clone {repo.url} --branch {repo.branch} {TMP_PATH}/{repo.name}")


def collect_test_stats(repo: Repo) -> dict[str, int]:
    """Look into `tests/integration` folder of repo and count usage of jubilan/pytest-operator."""
    test_files = glob.glob(f"{TMP_PATH}/{repo.name}/tests/integration/**/test_*.py", recursive=True)
    tests = []
    for test_file in test_files:
        raw = open(test_file).read()
        tests += re.findall(r"def.+?(test_[^(]+)\(([^)]+)\)", raw)
    counts = defaultdict(lambda: 0)
    for test in tests:
        if "OpsTest" in test[1] or "ops_test" in test[1]:
            counts["pytest-operator"] += 1
        elif "jubilant" in test[1] or "Juju" in test[1]:
            counts["jubilant"] += 1
        else:
            counts["unknown"] += 1
    return counts


def get_last_scheduled_run(repo: Repo) -> CIRun:
    """Return the last scheduled CI run state, i.e. looks for `ci.yaml/runs?event=schedule`."""
    resp = _get(repo, "actions/workflows/ci.yaml/runs?event=schedule")

    wf_run = resp["workflow_runs"][0]
    status = wf_run["status"]
    conclusion = wf_run["conclusion"]
    attempt = wf_run["run_attempt"]
    _id = int(wf_run["id"])
    url = wf_run["html_url"]
    should_retry = False

    if all([status == COMPLETED, conclusion != "success", attempt < 3]):
        should_retry = True

    return CIRun(id=_id, attempt=attempt, url=url, should_retry=should_retry, gh_data=wf_run)


def get_workflow(repo: Repo, workflow: str) -> dict[str, Any]:
    """Return workflow YAML definition of the given `repo` as a dict."""
    path = f"{TMP_PATH}/{repo.name}/.github/workflows/{workflow}.yaml"
    if os.path.exists(path):
        return yaml.safe_load(open(path).read())

    return {"jobs": {}}


# TODO: improve typing & docs.
def get_repos_wf_state(repos: Iterable[Repo]) -> list:
    """Read the repo .github/workflows directory and find which workflows are used."""
    lst = []
    for repo in repos:
        state = {"repo": f"{repo}", "group": repo.group}
        for workflow in ["ci", "release"]:
            parsed = get_workflow(repo, workflow)
            for job, def_ in parsed["jobs"].items():
                if "uses" in def_:
                    state[job] = _format_workflow_name(def_["uses"])
        stats = collect_test_stats(repo)
        state["jubilant"] = _format_test_stats(stats)
        lst.append(state)

    return lst


def get_open_issues(results: dict[str, list], repo: Repo, type_: Literal["pr", "issue"] = "pr"):
    """Get open issues/PRs for a given repo."""
    api = "pulls" if type_ == "pr" else "issues"
    res = _get(repo, f"{api}?state=open")
    raw = res if type_ == "pr" else [i for i in res if "draft" not in i]
    data = [
        {
            "repo": str(repo).replace("-operator", ""),
            "title": f"[{i['title']}]({i['html_url']})",
            "created": i["created_at"].replace("T", " ").replace("Z", " "),
            "updated": i["updated_at"].replace("T", " ").replace("Z", " "),
            "created_days": dtdiff(i["created_at"]),
            "updated_days": dtdiff(i["updated_at"]),
            "user": i["user"]["login"],
            "draft": i.get("draft", False),
        }
        for i in raw
    ]
    results.update({f"{repo}": data})


def collect_scheduled_ci_stats(repos: Iterable[Repo], last_n_days: int = 20) -> list:
    """Fetch data from repos to populate heatmap data object."""
    data = []
    for repo in repos:
        qenc = urlencode({"branch": repo.branch})
        resp = _get(repo, f"actions/workflows/ci.yaml/runs?{qenc}")
        rf_num = 0
        rf_denom = len(resp["workflow_runs"])
        if not rf_denom:
            continue
        for _run in resp["workflow_runs"]:
            rf_num += _run["run_attempt"] if _run["conclusion"] == "success" else 3
        rf = rf_num / rf_denom
        series = {
            "repo": f"{repo}",
            "group": repo.group,
            "name": f"{repo}",
            "rf": f"{rf:.3}",
            "data": [],
        }
        last_n = min(last_n_days, rf_denom)
        for i in range(last_n - 1, -1, -1):
            wf_run = resp["workflow_runs"][i]
            conclusion = wf_run["conclusion"]
            url = wf_run["html_url"]
            day = datetime.datetime.fromisoformat(wf_run["created_at"]).date()
            val = 100 if conclusion == "success" else 0
            series["data"].append({"x": str(day), "y": val, "url": url})

        data.append(series)
        logger.info(f"{repo} -- {series},")

    return data


def push_changes(
    repo: Repo,
    owner: str = OWNER,
    gh_email: str | None = None,
    gh_user: str | None = None,
    gh_token: str = BOT_TOKEN,
    gh_push_branch: str = "main",
    add: dict[str, str] = {},
    message: str = "update data",
    dry_run: bool = False,
):
    """Push changes to the git repo."""
    tmp_dir = tempfile.mkdtemp(dir=".", prefix=TMP_PREFIX)
    cred_prefix = f"{gh_user}:{gh_token}@" if all((gh_token, gh_user)) else ""

    git_repo = GitRepo.clone_from(  # pyright: ignore
        f"https://{cred_prefix}github.com/{repo.owner}/{repo.short_name}", tmp_dir, branch="main"
    )

    matches = re.findall(r"\[([0-9\-]+)\]", git_repo.head.commit.message)  # pyright: ignore
    last_date = matches[0] if matches else None
    current_date = f"{datetime.date.today()}"

    for file, dest in add.items():
        shutil.copyfile(file, f"{tmp_dir}/{dest}")
        git_repo.index.add([dest])  # pyright: ignore

    msg = f"ci: [{current_date}] {message}"

    if all((gh_user, gh_email)):
        with git_repo.config_writer() as cw:  # pyright: ignore
            cw.set_value("user", "name", gh_user)
            cw.set_value("user", "email", gh_email)
            cw.release()

    push_args = ["origin", gh_push_branch]
    if last_date != current_date:
        git_repo.index.commit(msg)  # pyright: ignore
    else:
        git_repo.git.commit(  # pyright: ignore
            "--amend",
            "-m",
            msg,
        )
        push_args = ["--force"] + push_args

    if dry_run:
        print(exec("git log --graph -n 3", cwd=tmp_dir))
        print(f"git push {' '.join(push_args)}")
    else:
        git_repo.git.push(*push_args)  # pyright: ignore


def strip_gh_link(link: str, owner: str = OWNER):
    """Remove GitHub domain and owner name from repo link."""
    return link.replace(f"https://github.com/{owner}/", "")
