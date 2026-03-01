"""Unit tests for `models` module."""

import pytest

from models import CharmSpec

DEFAULT_SPEC_MACHINE = {
    "name": "test-charm",
    "repo": "https://github.com/example/test-charm",
    "cmd": "workload --version",
    "substrate": "machine",
}

DEFAULT_SPEC_K8S = dict(DEFAULT_SPEC_MACHINE) | {"substrate": "k8s"}


@pytest.mark.parametrize(
    "in_",
    [
        ({}, False),
        ({"name": "test"}, False),
        ({**DEFAULT_SPEC_K8S}, False),
        ({**DEFAULT_SPEC_K8S, "rock": "test-rock"}, False),
        ({**DEFAULT_SPEC_K8S, "rock": "test-rock", "yaml_path": "testpath"}, True),
        (
            {**DEFAULT_SPEC_MACHINE, "substrate": "vm", "snap": "test", "code_path": "testpath"},
            False,
        ),  # no vm substrate, let's call it machine.
        ({**DEFAULT_SPEC_MACHINE, "snap": "test-snap"}, False),
        ({**DEFAULT_SPEC_MACHINE, "snap": "test-snap", "code_path": "testpath"}, True),
    ],
)
def test_charm_spec_validation(in_: tuple[dict, bool]):
    """Test `CharmSpec` validation functionality."""
    kwargs, valid = in_
    if valid:
        spec = CharmSpec(**kwargs)
        assert spec.name
    else:
        with pytest.raises((TypeError, ValueError)):
            spec = CharmSpec(**kwargs)
