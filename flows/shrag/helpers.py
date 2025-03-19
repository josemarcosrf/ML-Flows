import os
from pathlib import Path
from typing import Any

import importlib_metadata
import toml
from loguru import logger

from flows.shrag.schemas.answers import BaseAnswer


def get_or_raise(env_var: str) -> str:
    if var := os.getenv(env_var):
        return var

    raise ValueError(
        f"Cannot read environment variable '{env_var}'. Perhaps is not set?"
    )


def get_project_version():
    # Determine the source location of the package
    source_location = Path(__file__).parent

    # Path to the pyproject.toml file
    pyproject_path = source_location.parent / "pyproject.toml"

    if pyproject_path.exists():
        with Path.open(pyproject_path) as f:
            pyproject = toml.load(f)

            return pyproject["project"]["version"]
    else:
        # Fallback to importlib_metadata if not found
        return importlib_metadata.version("flows")


def get_aws_credentials() -> tuple[str, str]:
    """Fetches AWS credentials from the environment or session."""
    import boto3
    from botocore.exceptions import NoCredentialsError

    # Create a boto3 session
    session = boto3.Session()

    # Get credentials from the session
    try:
        credentials = session.get_credentials()
        return credentials.access_key, credentials.secret_key
    except (NoCredentialsError, AttributeError):
        raise RuntimeError("❌ No AWS credentials found in the environment or session.")

    # Access the key and secret


def print_sources(retrieved_nodes, print_text: bool = False):
    for node in retrieved_nodes:
        print(f"Document ID: {node.node.ref_doc_id} [node ID: {node.node.node_id}]")
        if print_text:
            print(f"Text: {node.node.text}")
        print(f"Score: {node.score}")
        print("---")


def parse_answer(res: BaseAnswer) -> dict[str, Any]:
    try:
        answer = res.response  # This is the BaseAnswer field
        if hasattr(answer, "value"):
            answer = answer.value
        return {
            "answer": answer,
            "confidence": res.confidence,
            "confidence_explanation": res.confidence_explanation,
        }
    except Exception as e:
        # Otherwise send an empty but structure respecting response
        logger.error(f"❌ Error parsing response! {e} (res: {res})")
        return {
            "answer": "ERROR",
            "confidence": 0,
            "confidence_explanation": "Error: {e}",
        }


def print_answer(res: BaseAnswer, explain: bool = False) -> None:
    print("A: {answer} (confidence={confidence})".format(**parse_answer(res)))
    if explain:
        print(f"Explanation: {res.confidence_explanation}")
