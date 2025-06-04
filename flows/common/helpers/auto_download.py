import copy
import inspect
import tempfile
import urllib.request
from functools import wraps
from pathlib import Path
from typing import Callable
from urllib.parse import unquote, urlparse

from loguru import logger

from flows.common.helpers.s3 import download_from_s3, is_s3_path


def is_url(path: str) -> bool:
    """Check if a path is a URL."""
    return path.startswith(("http://", "https://")) and not is_s3_path(path)


def download_from_url(url: str) -> Path | None:
    """Download a file from a URL and return the local path."""
    try:
        # Create a temporary file (preserving the original file name)
        # Extract the file name and strip URI parameters if present
        parsed_url = urlparse(url)
        fname = unquote(Path(parsed_url.path).name)
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir) / fname

        # Download the file
        urllib.request.urlretrieve(url, temp_path)

        return Path(temp_path)
    except Exception as e:
        raise Exception(f"💥 Error downloading from URL: {e}")


def download_if_remote(
    include: list[str] | None = None, exclude: list[str] | None = None
):
    """
    A decorator that downloads files from S3 or URLs if parameters are remote paths,
    with include and exclude filters. Works with Prefect's @flow and @task decorators.

    NOTE: Will only work on explicit parameters, not *args or **kwargs.

    Args:
        include (list[str] | None): List of parameter names to include.
            If None, include all.
        exclude (list[str] | None): List of parameter names to exclude.
            If None, exclude none.
    """
    if callable(include):
        # If the first argument is a function, it means the decorator is used
        # without parentheses. i.e.: @download_if_remote
        # In this case, we return the decorator with the default
        # include/exclude values
        return download_if_remote()(include)

    if include is None:
        include = []
    if exclude is None:
        exclude = []

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get the function signature
            sig = inspect.signature(func)
            # Combine args and kwargs
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            # Dictionary to store downloaded files and their original paths
            downloaded_files = {}

            def download_if_needed(path: str) -> Path | None:
                """Download a file if it's a remote path."""
                if is_s3_path(path):
                    return download_from_s3(path)
                elif is_url(path):
                    return download_from_url(path)
                return None

            def process_param(param_name, param_value):
                """Process a single parameter."""
                if isinstance(param_value, list):
                    # Deep copy the list to avoid modifying the original
                    bound_args.arguments[param_name] = copy.deepcopy(param_value)
                    for i, item in enumerate(param_value):
                        if isinstance(item, str):
                            if local_path := download_if_needed(item):
                                downloaded_files[f"{param_name}-{i}"] = {
                                    "original": item,
                                    "local": local_path,
                                }
                                bound_args.arguments[param_name][i] = str(local_path)

                elif isinstance(param_value, str):
                    if local_path := download_if_needed(param_value):
                        downloaded_files[param_name] = {
                            "original": param_value,
                            "local": local_path,
                        }
                        bound_args.arguments[param_name] = str(local_path)

            # Determine which parameters to check
            if include:
                params_to_check = {
                    k: v for k, v in bound_args.arguments.items() if k in include
                }
            if exclude:
                params_to_check = {
                    k: v for k, v in bound_args.arguments.items() if k not in exclude
                }
            if not include and not exclude:
                params_to_check = bound_args.arguments

            # Process each parameter
            for param_name, param_value in params_to_check.items():
                process_param(param_name, param_value)

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

        return wrapper

    return decorator
