"""Utilities to handle snaps & machine charms."""

import glob
import logging
import os
import re
import tempfile

import yaml

from util import POETRY, SANDBOX_EXEC, TMP_PREFIX, clone_repo, exec

logger = logging.getLogger(__name__)


def resolve_rev(spec: dict, charm_dir: str | None = None) -> int:
    """Resolve the snap revision of a machine charm."""
    tmp_path = tempfile.mkdtemp(dir=".", prefix=TMP_PREFIX)
    repo = spec["repo"]

    if not charm_dir:
        charm_dir = clone_repo(repo, path=tmp_path)

        logger.info("setting up venv...")
        exec(
            f"{POETRY} install", cwd=charm_dir, env={"POETRY_VIRTUALENVS_PATH": f"{tmp_path}/envs"}
        )

        envs = glob.glob(f"{tmp_path}/envs/**/site-packages", recursive=True)
    else:
        envs = glob.glob(f"{charm_dir}/**/site-packages", recursive=True)

    assert len(envs) == 1, "Error detecting the charm venv!"
    site_packages = envs[0]
    logger.info(f"will use {site_packages}")

    address = spec["rev_var_src_path"]
    pkg, var = address.split("::")

    rev = exec(
        f"python3 -c 'from {pkg} import {var}; print({var});'",
        cwd=charm_dir,
        env={"PYTHONPATH": f"{site_packages}/:src/:lib/"},
    ).strip()
    return int(rev)


def resolve_workload_version(spec, rev) -> str:
    """Resolve the workload version of a given `snap` at certain revision `rev`."""
    snap = spec["snap"]
    tmp_path = tempfile.mkdtemp(dir=".", prefix=TMP_PREFIX)
    logger.info(f"downloading snap {snap} @ {rev}...")
    exec(f"snap download {snap} --revision {rev}", cwd=tmp_path)
    raw_info = exec(f"unsquashfs -cat {snap}_{rev}.snap meta/snap.yaml", cwd=tmp_path)
    naive_version = yaml.safe_load(raw_info).get("version", "unknown")

    cmd = spec["cmd"]
    regex = spec["regex"]

    os.system(f"{SANDBOX_EXEC} snap install {snap} --revision {rev}")
    try:
        raw = exec(f"{SANDBOX_EXEC} {cmd}")
    except Exception as e:
        logger.error(e)
        os.system(f"{SANDBOX_EXEC} snap remove {snap}")
        return naive_version

    os.system(f"{SANDBOX_EXEC} snap remove {snap}")

    matches = [raw] if not regex else re.findall(regex, raw)
    version = matches[0].strip() if matches else naive_version

    logger.info(f"resolved workload version for {snap}@{rev}: {version}")
    return version


def resolve_machine_charm(spec: dict, charm_dir: str | None = None) -> tuple[int, str]:
    """Return the snap revision and workload version of a charm."""
    snap_rev = resolve_rev(spec, charm_dir=charm_dir)
    workload_version = resolve_workload_version(spec, snap_rev)
    return snap_rev, workload_version
