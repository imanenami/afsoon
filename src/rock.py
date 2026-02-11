"""Utilities to handle rocks & k8s charms."""

import logging
import os
import re
import secrets
import tempfile

from util import DOCKER, TMP_PREFIX, clone_repo, exec

logger = logging.getLogger(__name__)


def resolve_k8s_charm(spec: dict, charm_dir: str | None = None) -> str:
    """Return the workload version of a given charm spec."""
    tmp_path = tempfile.mkdtemp(dir=".", prefix=TMP_PREFIX)
    repo = spec["repo"]
    image_path = spec["image_path"]
    cmd = spec["cmd"]
    regex = spec["regex"]

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
