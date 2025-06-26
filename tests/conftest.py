import pytest
from dotenv import load_dotenv
from prefect import flow
from prefect.testing.utilities import prefect_test_harness

load_dotenv("dev.env")  # Load environment variables from dev.env


@flow
def my_flow(x):
    return x * 2


@pytest.fixture(autouse=False, scope="session")
def prefect_test_env():
    with prefect_test_harness():
        yield
