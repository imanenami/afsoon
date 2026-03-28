"""Utility and helper functions."""

import csv
import datetime
import json
import logging
import os
import secrets
import subprocess
from collections.abc import Iterable
from dataclasses import replace

import tenacity

from models import Artifact, CharmSpec, Repo

logger = logging.getLogger(__name__)

TMP_PREFIX = "tmp_jcmon_"
POETRY = "poetry"

if not os.environ.get("SANDBOX_INSTANCE", ""):
    inst = f"sandbox-{secrets.token_hex(8)}"
    logger.info(f"sandbox: {inst}")
    os.environ.update({"SANDBOX_INSTANCE": inst})


SANDBOX_INST = os.environ["SANDBOX_INSTANCE"].replace('"', "").replace("'", "")
DOCKER = f"lxc exec {SANDBOX_INST} -- docker"
SANDBOX_EXEC = f"lxc exec {SANDBOX_INST} --"

logger = logging.getLogger(__name__)


@tenacity.retry(
    after=tenacity.after_log(logger, logging.INFO),
    reraise=True,
    retry=tenacity.retry_if_exception_type(subprocess.TimeoutExpired),
    stop=tenacity.stop_after_attempt(5),
    wait=tenacity.wait_random(3, 10),
)
def exec(
    cmd: str, cwd: str | None = None, env: dict | None = None, timeout: float | None = None
) -> str:
    """Execute a command and capture STDERR."""
    try:
        return subprocess.check_output(
            cmd,
            shell=True,
            universal_newlines=True,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=env,
            timeout=timeout,
        )
    except subprocess.CalledProcessError as e:
        print(e.stderr, e.stdout)
        raise


def clone_repo(repo: str, path="") -> str:
    """Clone a repository to the given path, and return the full clone path."""
    path_ = f"{path.rstrip('/')}/" if path else ""
    base_name = repo.split("/")[-1]
    clone_path = f"{path_}{base_name}"
    logger.info("Cloning repo...")
    os.system(f"git clone {repo} {clone_path}")
    return clone_path


def keep_main_only(in_: Iterable[CharmSpec | Repo]) -> list[CharmSpec | Repo]:
    """Return a list of data classes (Repo or CharmSpec) keeping only the main branch."""
    out = []
    seen: set[str] = set()
    for item in in_:
        copy = replace(item, branch="main")
        if str(copy) in seen:
            continue
        seen.add(str(copy))
        out.append(copy)
    return out


def lxc_list() -> list[str]:
    """Run "lxc list" and return list of instance names."""
    _json = json.loads(exec("lxc list --format json"))
    return [i["name"] for i in _json]


def cleanup() -> None:
    """Clean up temp files and resources."""
    os.system(f"rm -rf ./{TMP_PREFIX}*")
    if SANDBOX_INST in lxc_list():
        os.system(f"lxc rm --force {SANDBOX_INST}")


def prepare_sandbox():
    """Check if sandbox instance is running, launch one if not."""
    ret_code = os.system(f"lxc exec {SANDBOX_INST} -- whoami")
    if not ret_code:
        logger.info(f"Sandbox instance {SANDBOX_INST} is running...")
        return

    os.system(f"scripts/init-sandbox.sh {SANDBOX_INST}")


def get_or_create_tmp_path() -> str:
    """Get the tmp path (saved into APP_TMP env. var) or creates it."""
    tmp_path = os.environ.get("TMP_PATH")
    if not tmp_path:
        tmp_path = f"{TMP_PREFIX}_app_{secrets.token_hex(4)}"
        os.environ.update({"TMP_PATH": tmp_path})

    os.makedirs(tmp_path, exist_ok=True)
    return tmp_path


def load_known_versions(file: str = ".known-versions") -> dict[Artifact, str]:
    """Load known artifact versions from the given CSV file."""
    state: dict[Artifact, str] = {}
    with open(file) as f:
        cols = f.readline().strip().split(",")
        reader = csv.DictReader(f, fieldnames=cols)
        for row in reader:
            artifact = Artifact(row["type"], row["name"], row["rev"])
            state[artifact] = row["version"]

    return state


def dtdiff(dt_str: str) -> int:
    """Return no. of days difference between a given datetime string repr. and today."""
    return int(
        (datetime.datetime.now(tz=datetime.UTC) - datetime.datetime.fromisoformat(dt_str)).days
    )
