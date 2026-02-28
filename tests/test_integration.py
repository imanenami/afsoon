import logging
import pytest


import snap
from models import CharmSpec
from util import cleanup, prepare_sandbox


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def with_sandbox():
    logger.debug("Preparing sandbox...")
    prepare_sandbox()
    yield
    logger.debug("Cleaning up...")
    cleanup()


@pytest.mark.integration
def test_machine_charm_workload_resolution(with_sandbox):
    test_spec = CharmSpec(
        substrate="machine",
        name="kafka",
        repo="https://github.com/canonical/kafka-operator",
        snap="charmed-kafka",
        code_path="literals::CHARMED_KAFKA_SNAP_REVISION",
        cmd="charmed-kafka.topics --version",
    )
    test_rev = 248

    versions = snap.resolve_machine_charm_single(test_spec, test_rev)
    assert versions.snap == 67
    assert versions.workload == "4.1.1-ubuntu2"
