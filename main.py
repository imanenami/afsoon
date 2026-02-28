"""Main module."""

import logging
import sys

import yaml

import rock
import snap
import workflows
from models import CharmSpec, WorkflowSettings
from util import cleanup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_config() -> dict[str, CharmSpec]:
    """Load charms.yaml."""
    charms = yaml.safe_load(open("charms.yaml"))
    cfg = {}
    for substrate in ("machine", "k8s"):
        charm_info = charms.get(substrate, [])
        for spec_dict in charm_info:
            spec = CharmSpec(substrate=substrate, **spec_dict)
            cfg[spec.name] = spec
    return cfg


def resolve_edge(charm_name: str):
    """Main function to resolve workload version of latest revision of a charm."""
    cfg = load_config()

    try:
        spec = cfg[charm_name]
        substrate = spec.substrate
        _resolve = (
            snap.resolve_machine_charm_single
            if substrate == "machine"
            else rock.resolve_k8s_charm_single
        )
        _resolve(spec)
    except Exception:
        raise
    finally:
        cleanup()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Workflow should be specified.")
        sys.exit(1)

    workflow = sys.argv[1].replace("-", "_")
    if workflow not in workflows.WORKFLOWS:
        print(f"Workflow {workflow} is not defined, available values are:")
        print("\n".join(workflows.WORKFLOWS.keys()))
        sys.exit(2)

    cfg = load_config()
    settings = WorkflowSettings(
        config=cfg,
    )

    workflows.run(workflow, settings)

    cleanup()
