"""Main module."""

import logging
import sys

import yaml

import workflows
from models import CharmSpec, WorkflowSettings
from util import cleanup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_charms() -> dict[str, CharmSpec]:
    """Load charms.yaml."""
    charms = yaml.safe_load(open("charms.yaml"))
    cfg = {}
    for substrate in ("machine", "k8s"):
        charm_info = charms.get(substrate, [])
        for spec_dict in charm_info:
            spec = CharmSpec(substrate=substrate, **spec_dict)
            cfg[spec.name] = spec
    return cfg


def load_rocks() -> list[str]:
    """Load rocks from ROCKS file."""
    raw = [line.strip() for line in open("ROCKS").readlines()]
    return [line for line in raw if line and not line.startswith("#")]


def _help() -> None:
    print("USAGE: main.py [WORKFLOW] or tox -e run workflow -- [WORKFLOW]")
    print("\nAvailable workflows are:")
    workflows.prettyprint()


def _quit(return_code: int):
    cleanup()
    sys.exit(return_code)


if __name__ == "__main__":
    if "-h" in sys.argv or "--help" in sys.argv:
        _help()
        _quit(0)

    if len(sys.argv) < 2:
        print("ERROR: workflow should be specified.\n")
        _help()
        _quit(1)

    workflow = sys.argv[1].replace("-", "_")
    if workflow not in workflows.WORKFLOWS:
        print(f'ERROR: Workflow "{workflow}" is not defined, available values are:')
        workflows.prettyprint()
        _quit(2)

    charms = load_charms()
    rocks = load_rocks()
    settings = WorkflowSettings(charms=charms, rocks=rocks)

    try:
        workflows.run(workflow, settings)
        _quit(0)
    except Exception as e:
        logger.error(f"Workflow finished with error:\n{e}")
        _quit(256)
