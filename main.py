"""Main module."""

import logging
import sys
from collections import namedtuple
from typing import Any

import yaml

import charm
import snap
from rock import resolve_k8s_charm
from util import cleanup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Versions = namedtuple("Versions", "charm snap workload")

# BLACKLIST = {"kafka-k8s/latest/edge", "kafka-k8s/latest/stable"}
BLACKLIST = set()

def load_config() -> dict[str, Any]:
    """Load charms.yaml."""
    charms = yaml.safe_load(open("charms.yaml"))
    cfg = {}
    for substrate in ("machine", "k8s"):
        charm_info = charms.get(substrate, [])
        cfg |= {i["name"]: dict(i) | {"substrate": substrate} for i in charm_info}
    return cfg


def load_charm_info(spec: dict) -> dict[str, str]:
    """Return a mapping of track/risk to charm revision for the given charm spec.

    The output will be like: {"4/edge": "100", "4/stable": "90", ...}
    """
    _charm = spec["name"]
    charm_info = charm.info(_charm)

    for k in BLACKLIST:
        rel = k.replace(f"{_charm}/", "")
        if rel in charm_info:
            charm_info.pop(rel)

    logger.info(charm_info)
    return charm_info


def _main_machine(spec: dict) -> list[Versions]:
    """Main entrypoint for machin charm specs."""
    _charm = spec["name"]
    charm_info = load_charm_info(spec)
    charm_revs = set(charm_info.values())

    rev_to_snap = {}
    for rev in charm_revs:
        charm_dir = charm.unpack(_charm, rev)
        try:
            rev_to_snap[rev] = snap.resolve_rev(spec, charm_dir)
        except AssertionError:
            rev_to_snap[rev] = "unknown"

    snap_revs = set(rev_to_snap.values())
    snap_to_workload = {}
    for rev in snap_revs:
        if rev == "unknown":
            snap_to_workload[rev] = "unknown"
        else:
            snap_to_workload[rev] = snap.resolve_workload_version(spec, rev)

    versions = []
    for rel, charm_rev in charm_info.items():
        snap_rev = rev_to_snap[charm_rev]
        wv = snap_to_workload[snap_rev]
        versions.append(Versions(charm=rel, snap=snap_rev, workload=wv))

    return versions


def _main_k8s(spec: dict) -> list[Versions]:
    """Main entrypoint for k8s charm specs."""
    _charm = spec["name"]
    charm_info = load_charm_info(spec)
    charm_revs = set(charm_info.values())

    rev_to_workload = {}
    for rev in charm_revs:
        charm_dir = charm.unpack(_charm, rev)
        try:
            rev_to_workload[rev] = resolve_k8s_charm(spec, charm_dir)
        except Exception as e:
            logger.error(e)
            rev_to_workload[rev] = "unknown"

    versions = []
    for rel, charm_rev in charm_info.items():
        wv = rev_to_workload[charm_rev]
        versions.append(Versions(charm=rel, snap=None, workload=wv))

    return versions


if __name__ == "__main__":
    cfg = load_config()

    try:
        _charm = sys.argv[1]
        spec = cfg[_charm]
        substrate = spec["substrate"]
        _main = _main_machine if substrate == "machine" else _main_k8s
        _main(spec)

    except Exception:
        raise
    finally:
        cleanup()
