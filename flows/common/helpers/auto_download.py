import inspect
import tempfile
import urllib.request
from functools import wraps
from pathlib import Path
from typing import Callable

from loguru import logger

from flows.common.helpers.s3 import download_from_s3, is_s3_path


def is_url(path: str) -> bool:
    """Check if a path is a URL."""
    return path.startswith(("http://", "https://")) and not is_s3_path(path)


def download_from_url(url: str) -> Path | None:
    """Download a file from a URL and return the local path."""
    try:
        # Create a temporary file
        _, temp_path = tempfile.mkstemp()

        # Download the file
        urllib.request.urlretrieve(url, temp_path)

        return Path(temp_path)
    except Exception as e:
        raise Exception(f"Error downloading from URL: {e}")


def download_if_remote(func: Callable) -> Callable:
    """
    A decorator that downloads files from S3 or URLs if parameters are remote paths.
    Works with Prefect's @flow and @task decorators.

    IMPORTANT: When using this decorator, make sure to use the @flow or @task decorator
    before this one, as this decorator modifies the function signature.

    Example usage:
    @flow
    @download_if_remote
    def process_file(file_path: str):
        # file_path will be a local path, even if an S3 or URL was provided
        ...
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        # Get the function signature
        sig = inspect.signature(func)
        # parameters = sig.parameters

        # Combine args and kwargs
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()

        # Dictionary to store downloaded files and their original paths
        downloaded_files = {}

        # Process each parameter
        for param_name, param_value in bound_args.arguments.items():
            # Skip parameters that are not strings
            if not isinstance(param_value, str):
                continue

            # Check if the parameter is a file path
            if is_s3_path(param_value):
                local_path = download_from_s3(param_value)
                if local_path:
                    downloaded_files[param_name] = {
                        "original": param_value,
                        "local": local_path,
                    }
                    bound_args.arguments[param_name] = str(local_path)
            elif is_url(param_value):
                local_path = download_from_url(param_value)
                if local_path:
                    downloaded_files[param_name] = {
                        "original": param_value,
                        "local": local_path,
                    }
                    bound_args.arguments[param_name] = str(local_path)

        try:
            # Call the original function with possibly modified arguments
            return func(*bound_args.args, **bound_args.kwargs)
        finally:
            # Clean up downloaded files
            for file_info in downloaded_files.values():
                try:
                    if file_info["local"].exists():
                        file_info["local"].unlink()
                except Exception as e:
                    logger.warning(
                        f"⚠️ Failed to clean up temporary file {file_info['local']}: {e}"
                    )

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    wrapper.__module__ = func.__module__
    wrapper.__qualname__ = func.__qualname__
    return wrapper
