import inspect
from pathlib import Path

from loguru import logger


def noop(*args, **kwargs):
    pass


def pub_and_log(client_id, pubsub: bool = False):
    from flows.common.clients.pubsub import UpdatePublisher

    if pubsub:
        pub = UpdatePublisher(client_id)

    def _pub_and_log(msg: str, doc_id: str | None = None, level: str = "info", **extra):
        # Get caller information using inspect.stack()
        frame_info = inspect.stack()[1]

        # Define a record patcher function that will modify the log record
        def patcher(record):
            module_name = frame_info.frame.f_globals.get("__name__", "<unknown>")
            fname = Path(frame_info.filename).name
            if fname == "__init__.py":
                fname = Path(frame_info.filename).parent.name
                fname = f"{fname}/f:{frame_info.function}"

            # We use the module-name/f:func-name as the file name in case of __init__.py
            # This is to make it easier to identify the Public Flow in the logs, which
            # is usually defined in the __init__.py file of a module.
            record["file"] = fname
            record["line"] = frame_info.lineno
            record["function"] = frame_info.function
            record["module"] = module_name
            return record

        # Append doc_id to the message if it is provided
        if doc_id:
            msg += f" (doc_id={doc_id})"

        # Get the logger with the patcher
        _logger = getattr(logger.patch(patcher), level, logger.info)
        _logger(msg)

        if pubsub:
            pub.publish_update(msg, doc_id, **extra)

    return _pub_and_log


def gather_files(file_or_dir: str, gather_glob: list[str]) -> list[str]:
    """If a directory is provided, it will recursively search for files
    matching the given glob patterns.
    If a single file is provided, it will be returned as a list.
    If a URL or S3 path is provided, it will be returned as a list.

    Args:
        file_or_dir (_type_): Single file / URL or directory to gather files form
        gather_glob (list[str]): List of glob patterns to match files in the directory

    Returns:
        list[str]: List of file paths
    """
    from flows.common.helpers.auto_download import is_url
    from flows.common.helpers.s3 import is_s3_path

    if is_url(file_or_dir) or is_s3_path(file_or_dir):
        print("🚀 Will automatically try to download file from URL or S3...")
        files = [file_or_dir]
    else:
        in_path = Path(file_or_dir)
        if in_path.is_dir():
            files = []
            print(f"📁 Gathering all files in dir {in_path}")
            for glob in gather_glob:
                print(f"🔍 Searching for {glob}...")
                files.extend([str(p) for p in in_path.rglob(glob)])
            if files:
                print(" - " + "\n - ".join(files) + "\n")
            else:
                print(f"🫙 No files found in {in_path} matching {gather_glob}")
        else:
            print("📄 Gathered a single file...")
            files = [file_or_dir]

    return files
