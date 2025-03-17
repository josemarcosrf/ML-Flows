import importlib
import inspect
import os
import sys
from pathlib import Path

from loguru import logger
from prefect import Flow

sys.tracebacklimit = int(os.getenv("TRACEBACK_LIMIT", 3))


# Define the log format
log_format = "[{time:YYYY-MM-DD HH:mm:ss}] | {level:<8} | {file}:{line} - {message}"

# Remove the default logger to prevent duplicate logs
logger.remove()

# Add a colored console handler
log_level_console = os.getenv("LOG_LEVEL", "INFO")
logger.add(
    sink=lambda msg: print(msg, end=""),
    format=log_format,
    level=log_level_console,
    colorize=True,
)

# Add a file handler with rotation
log_level_file = os.getenv("LOG_LEVEL_FILE", "INFO")
logger.add(
    "logs/flows.log",
    format=log_format,
    level=log_level_file,
    rotation="10 MB",  # Rotate after 10 MB
    retention=5,  # Keep the last 5 log files
    compression="zip",  # Compress rotated logs
)


def collect_public_flows() -> dict[str, Flow]:
    """This functions serves two purposes.
    1. Gathers all the flows in any submodule present in the "PUBLIC_FLOWS" dictionary
    2. Does the above without importing upon the 'flows' module init but on demand.
    This is to avoid importing Ray unecessarily or before patching at test time

    Returns:
        dict[str, Flow]: Mapping from 'flow name' to Flow for every public Flow found
    """
    public_flows = {}
    root_dir = Path()

    # Look for all the sub-modules (e.g.: dataflows.shrag, ...)
    for path in root_dir.rglob("flows/**/__init__.py"):
        # Construct the module name by joining path parts and replacing slashes with dots
        relative_path = path.relative_to(root_dir).with_suffix("")  # Remove .py suffix
        module_name = ".".join(relative_path.parts)  # Convert to dotted module name
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, "PUBLIC_FLOWS") and not inspect.ismodule(
                module.PUBLIC_FLOWS
            ):
                public_flows.update(module.PUBLIC_FLOWS)

        except ImportError as e:
            logger.error(f"Could not import {module_name}: {e}")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error accessing PUBLIC_FLOWS in {module_name}: {e}")

    return public_flows
