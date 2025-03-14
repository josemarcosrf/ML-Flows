import re
import tempfile
import urllib
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from loguru import logger


def is_valid_s3_uri(uri):
    """Validates a S3 URI using a regex pattern"""
    # Don't ask me to explain. This is chatGPT's magnificent ideation....
    s3_uri_regex = (
        r"^s3://(?!(?:.*\.\.)|(?:[-.]|.*[-.]$))([a-z0-9][a-z0-9.-]{1,61}[a-z0-9])/(.+)$"
    )
    return re.match(s3_uri_regex, uri) is not None


def is_s3_path(path: str) -> bool:
    """Check if a path is an S3 path."""
    return (path.startswith("s3://") and is_valid_s3_uri(path)) or (
        path.startswith("http") and "amazonaws.com" in path
    )


def parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    if not is_valid_s3_uri(s3_uri):
        raise ValueError(f"Invalid S3 URI: {s3_uri}")

    if s3_uri.startswith("s3://"):
        # Parse the S3 path
        parsed_url = urllib.parse.urlparse(s3_uri)
        bucket_name = parsed_url.netloc
        object_key = parsed_url.path.lstrip("/")
    else:
        # Handle http URLs to S3
        match = re.search(r"https?://([^.]+)\.s3\.amazonaws\.com/(.+)", s3_uri)
        if match:
            bucket_name = match.group(1)
            object_key = match.group(2)
        else:
            return None, None

    return bucket_name, object_key


def get_aws_credentials() -> tuple[str, str]:
    # Create a boto3 session
    session = boto3.Session()

    # Get credentials from the session
    credentials = session.get_credentials()

    # Access the key and secret
    return credentials.access_key, credentials.secret_key


def download_from_s3(s3_path: str) -> Path | None:
    """Download a file from S3 and return the local path."""
    try:
        bucket_name, object_key = parse_s3_uri(s3_path)
        if not bucket_name or not object_key:
            raise ValueError(f"Invalid S3 path: {s3_path}")

        # Create a temporary file
        _, temp_path = tempfile.mkstemp()

        # Download the file
        s3_client = boto3.client("s3")
        s3_client.download_file(bucket_name, object_key, temp_path)

        return Path(temp_path)
    except (NoCredentialsError, ClientError) as e:
        logger.error(f"💥 Error downloading from S3: {e}")
        return None
    except Exception as e:
        logger.error(f"💥 Unexpected error downloading from S3: {e}")
        return None
