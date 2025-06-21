import pytest
from prefect import flow
from prefect.testing.utilities import prefect_test_harness


@flow
def my_flow(x):
    return x * 2


@pytest.fixture(autouse=True, scope="session")
def prefect_test_env():
    with prefect_test_harness():
        yield
