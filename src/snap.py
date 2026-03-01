"""Utilities to handle snaps & machine charms."""

import glob
import logging
import os
import re
import tempfile

import yaml

import charm
from models import Artifact, CharmSpec, Versions
from util import POETRY, SANDBOX_EXEC, TMP_PREFIX, clone_repo, exec, load_known_versions

logger = logging.getLogger(__name__)


KNOWN = load_known_versions()


def resolve_rev(spec: CharmSpec, charm_dir: str | None = None) -> int:
    """Resolve the snap revision of a machine charm."""
    tmp_path = tempfile.mkdtemp(dir=".", prefix=TMP_PREFIX)
    repo = spec.repo

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

    default_cmd = (
        "import tomli; "
        'f = open("refresh_versions.toml", "rb"); '
        'print(tomli.load(f).get("snap", {}).get("revisions", {}).get("x86_64"))'
    )

    if spec.code_path == "default":
        pycmd = default_cmd
    else:
        address = f"{spec.code_path}"
        pkg, var = address.split("::")
        pycmd = f"from {pkg} import {var}; print({var});"

    rev = exec(
        f"python3 -c '{pycmd}'",
        cwd=charm_dir,
        env={"PYTHONPATH": f"{site_packages}/:src/:lib/"},
    ).strip()
    return int(rev)


def resolve_workload_version(spec: CharmSpec, rev) -> str:
    """Resolve the workload version of a given `snap` at certain revision `rev`."""
    snap = spec.snap
    artifact = Artifact(type="snap", name=spec.snap, rev=rev)
    if artifact in KNOWN:
        logger.info(f"Found {artifact} in known versions.")
        return KNOWN[artifact]

    tmp_path = tempfile.mkdtemp(dir=".", prefix=TMP_PREFIX)
    logger.info(f"downloading snap {snap} @ {rev}...")
    exec(f"snap download {snap} --revision {rev}", cwd=tmp_path)
    raw_info = exec(f"unsquashfs -cat {snap}_{rev}.snap meta/snap.yaml", cwd=tmp_path)
    naive_version = yaml.safe_load(raw_info).get("version", "unknown")

    os.system(f"{SANDBOX_EXEC} snap install {snap} --revision {rev}")
    try:
        raw = exec(f"{SANDBOX_EXEC} {spec.cmd}")
    except Exception as e:
        logger.error(e)
        os.system(f"{SANDBOX_EXEC} snap remove {snap}")
        return naive_version

    os.system(f"{SANDBOX_EXEC} snap remove {snap}")

    matches = [raw] if not spec.regex else re.findall(spec.regex, raw)
    version = matches[0].strip() if matches else naive_version

    logger.info(f"resolved workload version for {snap}@{rev}: {version}")
    return version


def resolve_machine_charm_single(spec: CharmSpec, charm_dir: str | None = None) -> tuple[int, str]:
    """Return the snap revision and workload version of a single charm/rev."""
    snap_rev = resolve_rev(spec, charm_dir=charm_dir)
    workload_version = resolve_workload_version(spec, snap_rev)
    return snap_rev, workload_version


def resolve_machine_charm_all(spec: CharmSpec) -> list[Versions]:
    """Resolve the snap revision and workload version of a family of charms (all active revs)."""
    _charm = spec.name
    charm_info = charm.info(_charm)
    charm_revs = set(charm_info.values())

    rev_to_snap = {}
    for rev in charm_revs:
        charm_dir = charm.unpack(_charm, rev)
        try:
            rev_to_snap[rev] = resolve_rev(spec, charm_dir)
        except AssertionError:
            rev_to_snap[rev] = "unknown"

    snap_revs = set(rev_to_snap.values())
    snap_to_workload = {}
    for rev in snap_revs:
        if rev == "unknown":
            snap_to_workload[rev] = "unknown"
        else:
            snap_to_workload[rev] = resolve_workload_version(spec, rev)

    versions = []
    for rel, charm_rev in charm_info.items():
        snap_rev = rev_to_snap[charm_rev]
        wv = snap_to_workload[snap_rev]
        versions.append(Versions(charm=rel, snap=snap_rev, image=None, workload=wv))

    return versions
