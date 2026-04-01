"""Main module."""

import logging
import sys
import traceback
from typing import Any

import yaml

import workflows
from models import CharmSpec, Repo, WorkflowSettings
from util import cleanup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_repos() -> list[Repo]:
    """Load repos from `sources.yaml` file."""
    with open("sources.yaml") as f:
        sources = yaml.safe_load(f)

    repos = []
    for dict_ in sources:
        for branch in dict_.get("branch", ["main"]):
            repos.append(Repo.from_dict(dict_, branch))

    return repos


def load_charms() -> dict[str, CharmSpec]:
    """Load charms from `sources.yaml` file."""
    with open("sources.yaml") as f:
        sources = yaml.safe_load(f)
    cfg = {}
    for spec_dict in sources:
        if "charm" not in spec_dict:
            continue
        for branch in spec_dict.get("branch", ["main"]):
            kv = dict(spec_dict)
            kv |= spec_dict["charm"]
            kv["ref"] = Repo.from_dict(spec_dict, branch)
            _ = kv.pop("charm")
            kv["branch"] = branch
            spec = CharmSpec(**{k: v for k, v in kv.items() if k in CharmSpec.__dataclass_fields__})
            unique_name = f"{spec.name}/{branch}"
            cfg[unique_name] = spec
    return cfg


def parse_workflow_params() -> dict[str, Any]:
    """Parse additional workflow params passed via CLI args."""
    if len(sys.argv) < 3:
        return {}

    ret = {}
    for kv in sys.argv[2:]:
        parts = kv.split("=")
        if len(parts) != 2:
            continue
        k = parts[0]
        v = parts[1].replace('"', "").replace("'", "")
        ret[k] = v

    return ret


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
    params = parse_workflow_params()

    if workflow not in workflows.registered():
        print(f'ERROR: Workflow "{workflow}" is not defined, available values are:')
        workflows.prettyprint()
        _quit(2)

    charms = load_charms()
    repos = load_repos()
    settings = WorkflowSettings(charms=charms, repos=repos, params=params)

    try:
        workflows.run(workflow, settings)
        _quit(0)
    except Exception:
        logger.error(f"Workflow finished with error:\n{traceback.format_exc()}")
        _quit(256)
