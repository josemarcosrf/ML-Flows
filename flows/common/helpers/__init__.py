def noop(*args, **kwargs):
    pass


def pub_and_log(client_id, pubsub: bool = False):
    from loguru import logger

    from flows.common.clients.pubsub import UpdatePublisher

    if pubsub:
        pub = UpdatePublisher(client_id)

    def _pub_and_log(msg: str, doc_id: str | None = None, level: str = "info", **extra):
        log_method = getattr(logger, level, logger.info)
        if doc_id:
            msg += f"(doc_id={doc_id})"

        log_method(msg)

        if pubsub:
            pub.publish_update(msg, doc_id, **extra)

    return _pub_and_log
