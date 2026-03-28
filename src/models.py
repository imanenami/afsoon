"""Models & data classes definition module."""

from collections import namedtuple
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any, Literal

Artifact = namedtuple("Artifact", "type name rev")
Versions = namedtuple("Versions", "charm snap image workload")
VersionMap = dict[str, int | str]


@dataclass(frozen=True)
class Repo:
    """Git repo repr. model."""

    url: str
    branch: str = "main"
    owner: str = "canonical"
    group: str = "kafka"
    workflows: frozenset[str] = frozenset([])

    @cached_property
    def short_name(self) -> str:
        """GitHub repo name after removing the base URL and owner."""
        return self.url.rstrip("/").split("/")[-1]

    @cached_property
    def name(self) -> str:
        """A name to represent the repo/branch combination, e.g. kafka--3-edge."""
        _branch = self.branch.replace("/", "-")
        return f"{self.short_name}--{_branch}"

    @classmethod
    def from_dict(cls, dict_: dict, branch: str) -> "Repo":
        """Create Repo from a given dict & branch."""
        return cls(
            url=dict_["repo"],
            group=dict_["group"],
            branch=branch,
            workflows=frozenset(dict_.get("workflows", [])),
        )

    def __str__(self) -> str:
        """Display name of a Repo."""
        _postfix = "" if self.branch == "main" else f" [{self.branch}]"
        return f"{self.short_name.replace('-operator', '')}{_postfix}"


@dataclass
class CharmSpec:
    """Charm specification data model."""

    ref: Repo
    substrate: Literal["machine", "k8s"]
    group: str
    name: str
    repo: str
    branch: str
    cmd: str
    yaml_path: str | None = None
    code_path: list[str] = field(default_factory=list)
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

    def __str__(self) -> str:
        """Unique string repr. of the charm specification."""
        return f"{self.name} [{self.branch}]"


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
    repos: list[Repo]
    params: dict[str, Any]
