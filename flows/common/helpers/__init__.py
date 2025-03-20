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
