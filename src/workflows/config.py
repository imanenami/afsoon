"""Workflow definitions."""

import json
import logging

from models import WorkflowSettings
from util import keep_main_only

from .base import push_to_remote, register

logger = logging.getLogger(__name__)


@register(aliases=["config"])
def generate_config(settings: WorkflowSettings) -> None:
    """Generate `charms.js` config file for the FE application."""
    charms = keep_main_only(settings.charms.values())
    raw = [
        {
            "name": c.name,
            "group": c.group,
            "repo": getattr(c, "repo"),
            "substrate": getattr(c, "substrate"),
        }
        for c in charms
    ]
    js = f"charms = {json.dumps(raw, indent=4)};"
    with open("charms.js", "w") as f:
        f.write(js)

    push_to_remote(add={"charms.js": "js/charms.js"})
