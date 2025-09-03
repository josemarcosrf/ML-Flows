import os

import pytest
from prefect import flow
from prefect.testing.utilities import prefect_test_harness

# Set required env vars before any imports or tests
os.environ["DOCLING_BASE_URL"] = "http://localhost:8000/docling"
os.environ["REDIS_PWD"] = "testpwd"
os.environ["CHROMA_COLLECTION"] = "test_collection"
os.environ["MONGO_URI"] = "mongodb://localhost:27017"
os.environ["MONGO_DB"] = "test_db"
os.environ["VISION_MODEL"] = "test-vision-model"
os.environ["OPENAI_API_KEY"] = "test-openai-key"
os.environ["AWS_ACCESS_KEY_ID"] = "test-aws-key"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test-aws-secret"
os.environ["AWS_REGION"] = "us-east-1"


@flow
def my_flow(x):
    return x * 2


@pytest.fixture(autouse=False, scope="session")
def prefect_test_env():
    with prefect_test_harness():
        yield
