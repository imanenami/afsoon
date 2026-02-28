"""Utility and helper functions."""

import logging
import os
import subprocess

TMP_PREFIX = "tmp_imon_"
POETRY = "poetry"
DOCKER = "lxc exec sqlpad -- docker"
SANDBOX_EXEC = "lxc exec sandbox --"

logger = logging.getLogger(__name__)


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


def cleanup() -> None:
    """Clean up temp files and resources."""
    os.system(f"rm -rf ./{TMP_PREFIX}*")
