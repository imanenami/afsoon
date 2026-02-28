"""Utilities to handle charms and juju commands."""

import json
import logging
import tempfile

from models import VersionMap
from util import TMP_PREFIX, exec

logger = logging.getLogger(__name__)


def info(charm: str) -> VersionMap:
    """Run `juju info` command and return a mapping of track/risk: revision.

    The output will be like: {"4/edge": "100", "4/stable": "90", ...}
    """
    info = json.loads(exec(f"juju info {charm} --format json"))

    releases = {}
    for channel in info["channels"]:
        for risk, release in info["channels"][channel].items():
            releases[f"{channel}/{risk}"] = release

    return {rel: details[0]["revision"] for rel, details in releases.items()}


def unpack(charm: str, rev: int | str) -> str:
    """Download and unpack a charm at certain revision, return the unpacked path."""
    tmp_path = tempfile.mkdtemp(dir=".", prefix=TMP_PREFIX)
    logger.info(f"Downloading {charm} @ {rev}")
    exec(f"juju download {charm} --revision {rev}", cwd=tmp_path, timeout=30)
    exec(f"unzip ./{charm}_r{rev}.charm -d {charm}_r{rev}", cwd=tmp_path)
    return f"{tmp_path}/{charm}_r{rev}"
