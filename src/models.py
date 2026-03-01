"""Models & data classes definition module."""

from collections import namedtuple
from dataclasses import dataclass, field
from typing import Literal

Artifact = namedtuple("Artifact", "type name rev")
Versions = namedtuple("Versions", "charm snap image workload")
VersionMap = dict[str, int | str]


@dataclass
class CharmSpec:
    """Charm specification data model."""

    substrate: Literal["machine", "k8s"]
    name: str
    repo: str
    cmd: str
    yaml_path: str | None = None
    code_path: str | None = None
    regex: str | None = None
    snap: str | None = None
    rock: str | None = None
    healthy: str = "true"

    def __post_init__(self):
        """Validate model consistency."""
        if self.substrate == "machine":
            if not all([self.code_path, self.snap]):
                raise ValueError('"snap" & "code_path" should be defined for machine charms.')
        elif self.substrate == "k8s":
            if not all([self.yaml_path]):
                raise ValueError('"yaml_path" should be defined for k8s charms.')
        else:
            raise ValueError(f"Unsupported substrate: {self.substrate}")

    @property
    def is_healthy(self):
        """Is the CI healthy?"""
        return self.healthy == "true"


@dataclass
class CIRun:
    """CI run status data model."""

    id: int
    attempt: int
    url: str
    should_retry: bool = False
    gh_data: dict = field(default_factory=dict)


@dataclass
class WorkflowSettings:
    """Workflow settings data model."""

    charms: dict[str, CharmSpec]
    rocks: list[str]
