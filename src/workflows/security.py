"""Workflow definitions."""

import datetime
import inspect
import json
import logging
import os

import trivy
from models import WorkflowSettings
from util import SANDBOX_INST, prepare_sandbox

from .base import push_to_remote, register

logger = logging.getLogger(__name__)


@register(aliases=["scan"])
def trivy_scan(settings: WorkflowSettings) -> None:
    """Build from source and run Trivy scan on the rocks defined in "ROCKS" file."""
    prepare_sandbox()
    # install Trivy snap on sandbox
    os.system(f"lxc exec {SANDBOX_INST} -- snap install --classic trivy")
    repos = [repo for repo in settings.repos if "scan" in repo.workflows]
    for src in repos:
        url = src.url.rstrip("/")
        os.system(f"scripts/vuln-scan.sh {SANDBOX_INST} {url} {src.branch} {src.group}")
    vuln_list = trivy.combine_results()
    now = datetime.datetime.now(tz=datetime.UTC).replace(microsecond=0)
    raw = inspect.cleandoc(f"""
        updatedAt = '{now}';
        rawVulnData = {json.dumps(vuln_list)};
    """)

    with open("vulnData.js", "w") as f:
        f.write(raw)

    push_to_remote(add={"vulnData.js": "js/vulnData.js"})
