"""Workflow definitions."""

import logging
import os
from collections import defaultdict
from collections.abc import Callable, Iterable
from functools import wraps

from models import Repo, WorkflowSettings

logger = logging.getLogger(__name__)


_WORKFLOWS = {}


def configured(repo: Repo, workflows: Iterable[str]) -> bool:
    """Check if either of given workflows are configured for a given repo."""
    for workflow in workflows:
        if workflow in repo.workflows:
            return True

    return False


def prettyprint() -> None:
    """Pretty print workflows and their docs to stdout."""
    alias_map = defaultdict(lambda: [])
    for label, func in _WORKFLOWS.items():
        alias_map[func].append(label)

    for func, aliases in alias_map.items():
        aliases.sort()
        quoted = [f'"{alias}"' for alias in aliases]
        doc_lines = [line.strip() for line in func.__doc__.split("\n") if line.strip()]
        print(f"  - {', '.join(quoted)}:", " ".join(doc_lines))


# push_to_remote = partial(
#     github.push_changes,
#     Repo("kafka-ci", owner="imanenami"),
#     gh_user="iminions",
#     gh_email="iman@datapy.co",
# )


def push_to_remote(add: dict[str, str] = {}):
    """Dev. implementation of push_to_kafka_ci."""
    for k, v in add.items():
        os.system(f"cp {k} /var/www/html/kafka-ci/{v}")


def registered() -> list[str]:
    """Return list of registered workflows."""
    return list(_WORKFLOWS.keys())


def register(aliases: Iterable[str] = []):
    """Register a workflow with given aliases."""

    def decorator(f: Callable[[WorkflowSettings], None]):
        global _WORKFLOWS
        nonlocal aliases
        _aliases = [f.__qualname__, f.__qualname__.replace("_", "-"), *aliases]
        for alias in _aliases:
            _WORKFLOWS[alias] = f

        @wraps(f)
        def wrapper(*args, **kwargs):
            return f(*args, **kwargs)

        return wrapper

    return decorator


def run(workflow: str, settings: WorkflowSettings) -> None:
    """Run a workflow with given settings.

    Args:
        workflow (str): workflow name/label.
        settings (WorkflowSettings): workflow settings.

    Raises:
        RuntimeError: if workflow is not defined.
    """
    if workflow not in _WORKFLOWS:
        raise RuntimeError(f"Workflow {workflow} is not defined")

    _WORKFLOWS[workflow](settings)
