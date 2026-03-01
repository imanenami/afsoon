"""Utilities to handle rocks & k8s charms."""

import logging
import os
import re
import secrets

import charm
from models import Artifact, CharmSpec, Versions
from util import DOCKER, exec, load_known_versions

logger = logging.getLogger(__name__)

KNOWN = load_known_versions()


def resolve_k8s_charm_single(spec: CharmSpec, rev: int | str) -> tuple[str, str]:
    """Return the workload version of a given charm spec - single revision."""
    image_path = spec.yaml_path
    cmd = spec.cmd
    regex = spec.regex

    charm_dir = charm.unpack(spec.name, rev)

    image = exec(f"cat {charm_dir}/metadata.yaml | yq -r '{image_path}'").strip()
    artifact = Artifact(type="rock", name=spec.name, rev=image)
    if artifact in KNOWN:
        return image, KNOWN[artifact]

    container = f"testrock_{secrets.token_hex(8)}"
    os.system(f"{DOCKER} run -d --name {container} {image}")
    raw = exec(f"{DOCKER} exec {container} {cmd}")

    matches = [raw] if not regex else re.findall(regex, raw)
    if not matches:
        return image, "unknown"

    # clean up
    os.system(f"{DOCKER} rm --force {container}")

    return image, matches[0].strip()


def resolve_k8s_charm_all(spec: CharmSpec) -> list[Versions]:
    """Return the workload version of a given charm spec - all revisions."""
    _charm = spec.name
    charm_info = charm.info(_charm)
    charm_revs = set(charm_info.values())

    rev_to_workload = {}
    for rev in charm_revs:
        try:
            rev_to_workload[rev] = resolve_k8s_charm_single(spec, rev)
        except Exception as e:
            logger.error(e)
            rev_to_workload[rev] = ("unknown", "unknown")

    versions = []
    for rel, charm_rev in charm_info.items():
        image, wv = rev_to_workload[charm_rev]
        versions.append(Versions(charm=rel, snap=None, image=image, workload=wv))

    return versions
