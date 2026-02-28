"""Models & data classes definition module."""

from collections import namedtuple
from dataclasses import dataclass, field
from typing import Literal

Versions = namedtuple("Versions", "charm snap workload")
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
    """..."""

    config: dict[str, CharmSpec]
    repos: list[str]
