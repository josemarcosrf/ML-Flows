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
        raise Exception(f"💥 Error downloading from URL: {e}")


# def download_if_remote(func: Callable) -> Callable:
#     """
#     A decorator that downloads files from S3 or URLs if parameters are remote paths.
#     Works with Prefect's @flow and @task decorators.

#     IMPORTANT: When using this decorator, make sure to use the @flow or @task decorator
#     before this one, as this decorator modifies the function signature.

#     Example usage:
#     @flow
#     @download_if_remote
#     def process_file(file_path: str):
#         # file_path will be a local path, even if an S3 or URL was provided
#         ...
#     """

#     @wraps(func)
#     def wrapper(*args, **kwargs):
#         # Get the function signature
#         sig = inspect.signature(func)
#         # parameters = sig.parameters

#         # Combine args and kwargs
#         bound_args = sig.bind(*args, **kwargs)
#         bound_args.apply_defaults()

#         # Dictionary to store downloaded files and their original paths
#         downloaded_files = {}

#         # Process each parameter
#         for param_name, param_value in bound_args.arguments.items():
#             # Skip parameters that are not strings
#             if not isinstance(param_value, str):
#                 continue

#             # Check if the parameter is a file path
#             if is_s3_path(param_value):
#                 local_path = download_from_s3(param_value)
#                 if local_path:
#                     downloaded_files[param_name] = {
#                         "original": param_value,
#                         "local": local_path,
#                     }
#                     bound_args.arguments[param_name] = str(local_path)
#             elif is_url(param_value):
#                 local_path = download_from_url(param_value)
#                 if local_path:
#                     downloaded_files[param_name] = {
#                         "original": param_value,
#                         "local": local_path,
#                     }
#                     bound_args.arguments[param_name] = str(local_path)

#         try:
#             # Call the original function with possibly modified arguments
#             return func(*bound_args.args, **bound_args.kwargs)
#         finally:
#             # Clean up downloaded files
#             for file_info in downloaded_files.values():
#                 try:
#                     if file_info["local"].exists():
#                         file_info["local"].unlink()
#                 except Exception as e:
#                     logger.warning(
#                         f"⚠️ Failed to clean up temporary file {file_info['local']}: {e}"
#                     )

#     return wrapper


def download_if_remote(
    include: list[str] | None = None, exclude: list[str] | None = None
):
    """
    A decorator that downloads files from S3 or URLs if parameters are remote paths,
    with include and exclude filters. Works with Prefect's @flow and @task decorators.

    Args:
        include (list[str] | None): List of parameter names to include. If None, include all.
        exclude (list[str] | None): List of parameter names to exclude. If None, exclude none.
    """
    if callable(include):
        # If the first argument is a function, it means the decorator is used without parentheses
        # i.e.: @download_if_remote
        # In this case, we return the decorator with the default include/exclude values
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
                    for i, item in enumerate(param_value):
                        if isinstance(item, str):
                            local_path = download_if_needed(item)
                            if local_path:
                                downloaded_files[param_name] = {
                                    "original": item,
                                    "local": local_path,
                                }
                                param_value[i] = str(local_path)
                elif isinstance(param_value, str):
                    local_path = download_if_needed(param_value)
                    if local_path:
                        downloaded_files[param_name] = {
                            "original": param_value,
                            "local": local_path,
                        }
                        bound_args.arguments[param_name] = str(local_path)

            # Determine which parameters to check
            params_to_check = (
                kwargs
                if include
                else {k: v for k, v in kwargs.items() if k not in exclude}
            )

            # Process each parameter
            for param_name, param_value in params_to_check.items():
                if param_name in include or not include:
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


if __name__ == "__main__":
    # Test the decorators
    @download_if_remote()
    def test_download_if_remote(
        many_files: list[str], file_path: str, other_param: str
    ):
        for fpath in many_files:
            logger.info(f"👋 Processing file: {fpath}")

        # logger.info(f"🔚 Finally file: {file_path} and other param: {other_param}")

    file_paths = [
        "s3://my-bucket/my-file.txt",
        "https://example.com/my-file.txt",
        "local-file.txt",
    ]
    for fpath in file_paths:
        try:
            test_download_if_remote(
                file_paths, file_path=fpath, other_param="something"
            )
        except Exception as e:
            logger.error(f"👎 Error processing file: {fpath}: {e}")
