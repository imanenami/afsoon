"""Utilities to handle rocks & k8s charms."""

import logging
import os
import re
import secrets
import tempfile

import charm
from models import CharmSpec, Versions
from util import DOCKER, TMP_PREFIX, clone_repo, exec

logger = logging.getLogger(__name__)


def resolve_k8s_charm_single(spec: CharmSpec, charm_dir: str | None = None) -> str:
    """Return the workload version of a given charm spec - single revision."""
    tmp_path = tempfile.mkdtemp(dir=".", prefix=TMP_PREFIX)
    repo = spec.repo
    image_path = spec.yaml_path
    cmd = spec.cmd
    regex = spec.regex

    if not charm_dir:
        charm_dir = clone_repo(repo, tmp_path)

    image = exec(f"cat {charm_dir}/metadata.yaml | yq -r '{image_path}'").strip()
    container = f"testrock_{secrets.token_hex(8)}"
    os.system(f"{DOCKER} run -d --name {container} {image}")
    raw = exec(f"{DOCKER} exec {container} {cmd}")

    matches = [raw] if not regex else re.findall(regex, raw)
    assert matches, "Can't determine workload version!"

    # clean up
    os.system(f"rm -rf {tmp_path}")
    os.system(f"{DOCKER} rm --force {container}")

    return matches[0].strip()


def resolve_k8s_charm_all(spec: CharmSpec) -> list[Versions]:
    """Return the workload version of a given charm spec - all revisions."""
    _charm = spec.name
    charm_info = charm.info(_charm)
    charm_revs = set(charm_info.values())

    rev_to_workload = {}
    for rev in charm_revs:
        charm_dir = charm.unpack(_charm, rev)
        try:
            rev_to_workload[rev] = resolve_k8s_charm_single(spec, charm_dir)
        except Exception as e:
            logger.error(e)
            rev_to_workload[rev] = "unknown"

    versions = []
    for rel, charm_rev in charm_info.items():
        wv = rev_to_workload[charm_rev]
        versions.append(Versions(charm=rel, snap=None, workload=wv))

    return versions
