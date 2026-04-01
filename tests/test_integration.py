"""Integration tests."""

import logging

import pytest

import rock
import snap
from models import CharmSpec, Repo
from util import cleanup, prepare_sandbox

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def with_sandbox():
    """Prepare a sandbox for tests."""
    logger.debug("Preparing sandbox...")
    prepare_sandbox()
    yield
    logger.debug("Cleaning up...")
    cleanup()


@pytest.mark.integration
def test_machine_charm_workload_resolution(with_sandbox):
    """Test `snap.resolve_machine_charm_single` resolves snap & workload versions properly."""
    test_spec = CharmSpec(
        substrate="machine",
        group="kafka",
        name="kafka",
        branch="main",
        ref=Repo(url="https://github.com/canonical/kafka-operator"),
        repo="https://github.com/canonical/kafka-operator",
        snap="charmed-kafka",
        code_path=["literals::CHARMED_KAFKA_SNAP_REVISION"],
        cmd="charmed-kafka.topics --version",
    )
    test_rev = 248

    versions = snap.resolve_machine_charm_single(test_spec, test_rev)
    assert versions.snap == 67
    assert versions.workload == "4.1.1-ubuntu2"


@pytest.mark.integration
def test_k8s_charm_workload_resolution(with_sandbox):
    """Test `rock.resolve_k8s_charm_single` resolves workload versions properly."""
    test_spec = CharmSpec(
        substrate="k8s",
        group="kafka",
        name="postgresql-k8s",
        branch="16/edge",
        ref=Repo(url="https://github.com/canonical/postgresql-k8s-operator"),
        repo="https://github.com/canonical/postgresql-k8s-operator",
        yaml_path='.resources."postgresql-image"."upstream-source"',
        regex=r"[0-9]+.[0-9]+",
        cmd="psql --version",
    )
    test_rev = 774

    image, version = rock.resolve_k8s_charm_single(test_spec, test_rev)
    assert image
    assert version == "14.20"
