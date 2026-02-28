import pytest

from models import CharmSpec


DEFAULT_SPEC = {"name": "test-charm", "repo": "https://github.com/example/test-charm", "cmd": "workload --version"}


@pytest.mark.parametrize(
    "in_",
    [
        ({}, False),
        ({"name": "test"}, False),
        ({**DEFAULT_SPEC, "substrate": "k8s"}, False),
        ({**DEFAULT_SPEC, "substrate": "k8s", "rock": "test-rock"}, False),
        ({**DEFAULT_SPEC, "substrate": "k8s", "rock": "test-rock", "yaml_path": "testpath"}, True),
        ({**DEFAULT_SPEC, "substrate": "vm", "snap": "test-snap", "code_path": "testpath"}, False),  # no vm substrate
        ({**DEFAULT_SPEC, "substrate": "machine", "snap": "test-snap"}, False),
        ({**DEFAULT_SPEC, "substrate": "machine", "snap": "test-snap", "code_path": "testpath"}, True),
    ]
)
def test_charm_spec_validation(in_: tuple[dict, bool]):
    kwargs, valid = in_
    if valid:
        spec = CharmSpec(**kwargs)
        assert spec.name
    else:
        with pytest.raises((TypeError, ValueError)):
            spec = CharmSpec(**kwargs)
