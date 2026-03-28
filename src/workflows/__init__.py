"""Workflow definitions."""

import logging

from .base import prettyprint, registered, run
from .config import generate_config
from .heatmap import generate_heatmap
from .open_issues import open_issues
from .poke import poke_ci
from .releases import gather_releases
from .security import trivy_scan

logger = logging.getLogger(__name__)


__all__ = [
    "gather_releases",
    "generate_config",
    "generate_heatmap",
    "open_issues",
    "poke_ci",
    "prettyprint",
    "registered",
    "run",
    "trivy_scan",
]
