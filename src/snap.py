"""Utilities to handle snaps & machine charms."""

import glob
import logging
import os
import re
import tempfile
from subprocess import CalledProcessError

import yaml

import charm
from models import Artifact, CharmSpec, Versions
from util import POETRY, SANDBOX_EXEC, TMP_PREFIX, clone_repo, exec, load_known_versions

logger = logging.getLogger(__name__)


KNOWN = load_known_versions()
DEFAULT_PYCMD = (
    "import tomli; "
    'f = open("refresh_versions.toml", "rb"); '
    'print(tomli.load(f).get("snap", {}).get("revisions", {}).get("x86_64"))'
)


def _resolve_code_path(code_path: str, charm_dir: str, venv: str = "") -> str:
    if code_path == "default":
        pycmd = DEFAULT_PYCMD
    else:
        address = f"{code_path}"
        pkg, var = address.split("::")
        pycmd = f"import {pkg}; print({pkg}.{var});"

    try:
        return exec(
            f"python3 -c '{pycmd}'",
            cwd=charm_dir,
            env={"PYTHONPATH": f"src/:lib/:{venv}"},
        ).strip()
    except CalledProcessError as e:
        logger.error(e)
        raise RuntimeError("Version detection failed!")


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

    if len(envs) != 1:
        raise RuntimeError("Error detecting the charm venv!")

    venv = envs[0]
    for code_path in spec.code_path:
        try:
            return int(_resolve_code_path(code_path=code_path, charm_dir=charm_dir, venv=venv))
        except RuntimeError:
            continue

    raise RuntimeError(
        f"Snap version resolution failed after evaluating {len(spec.code_path)} alternatives."
    )


def resolve_workload_version(spec: CharmSpec, rev) -> str:
    """Resolve the workload version of a given `snap` at certain revision `rev`."""
    snap = spec.snap
    artifact = Artifact(type="snap", name=spec.snap, rev=str(rev))
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


def resolve_machine_charm_single(spec: CharmSpec, rev: int) -> Versions:
    """Return the snap revision and workload version of a single charm/rev."""
    charm_dir = charm.unpack(spec.name, rev)
    snap_rev = resolve_rev(spec, charm_dir=charm_dir)
    workload_version = resolve_workload_version(spec, snap_rev)
    return Versions(charm=spec.name, snap=snap_rev, image=None, workload=workload_version)


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
        except RuntimeError:
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
