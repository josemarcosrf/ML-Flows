import uuid
from datetime import datetime
from hashlib import sha1
from pathlib import Path
from urllib.parse import unquote, urlparse

from loguru import logger
from prefect import Flow, flow
from prefect.runtime import flow_run

from flows.common.clients.mongo import MongoDBClient
from flows.common.clients.vector_stores import get_default_vector_collection_name
from flows.common.helpers import pub_and_log
from flows.common.helpers.auto_download import download_if_remote
from flows.common.types import DBDocumentInfo, DOC_STATUS
from flows.settings import settings


def custom_index_flow_run_name() -> str:
    """Generate a custom flow run name for indexing files"""

    function_name = flow_run.get_flow_name()
    parameters = flow_run.get_parameters()

    client_id = parameters.get("client_id", "unknown")
    file_path_param = parameters.get("file_path", "unknown")
    doc_name = parameters.get("metadata", {}).get("file_name")
    if not doc_name:
        # If no file name is provided, derive it from the file path
        parsed = urlparse(file_path_param)
        if parsed.scheme and parsed.netloc:
            # It's a URI, strip query and decode
            path = unquote(parsed.path)
            fpath = Path(path)
        else:
            # Local file path
            fpath = Path(file_path_param)

        doc_name = fpath.stem

    return f"{function_name}={doc_name} ({client_id})"


@flow(
    log_prints=True,
    flow_run_name=custom_index_flow_run_name,
)
@download_if_remote(include=["file_path"])
def index_document_file(
    client_id: str,
    file_path: str,
    embedding_model_id: str = settings.EMBEDDING_MODEL,
    chunk_size: int = settings.CHUNK_SIZE,
    chunk_overlap: int = settings.CHUNK_OVERLAP,
    llm_backend: str = settings.LLM_BACKEND,
    vector_store_backend: str = settings.VECTOR_STORE_BACKEND,
    pubsub: bool = False,
    metadata: dict | None = None,
):
    """Index a single file in the data directory

    Args:
        client_id (str): external ID of the client, used to identify the
            documents and results in the MongoDB collection.
        file_path (str): File URI or path to index
        embedding_model_id (str, optional): ID of the embedding model to use.
        chunk_size (int, optional): Size of the chunks to split the document into.
        chunk_overlap (int, optional): Overlap between the chunks.
        llm_backend (str, optional): LLM backend to use.
        vector_store_backend (str, optional): Vector store backend to use.
        pubsub (bool, optional): Whether to use Pub/Sub for updates.
            Defaults to False.
        metadata (dict, optional): Metadata dictionary for the file.
    """
    from flows.preproc.index import index_file

    def update_doc_db(doc_id: str, update: dict, upsert=False):
        res = db.update_one(
            settings.MONGO_DOC_COLLECTION,
            filter={"id": doc_id, "client_id": client_id},
            update=update,
            upsert=upsert,
        )
        logger.debug(f"DB update results: {res}")

    # metadata is any user defined data for the document; e.g. project_id, name, etc.
    # We ensure it also has a client_id field so it get's stored in the vectors DB
    if metadata is None:
        metadata = {"client_id": client_id}
    else:
        metadata = {**metadata, "client_id": client_id}

    pub = pub_and_log(client_id, pubsub)
    db = MongoDBClient()

    collection_name = get_default_vector_collection_name(
        vector_store_backend=vector_store_backend,
        client_id=client_id,
        llm_backend=llm_backend,
        embedding_model_id=embedding_model_id,
    )

    fpath = Path(file_path).resolve()
    doc_id = str(uuid.uuid4())
    doc_sha = sha1(fpath.open("rb").read()).hexdigest()
    doc_name = metadata.get("file_name") or fpath.stem

    # doc ctx is used for logging and pub/sub messages
    doc_ctx = {
        "doc_name": doc_name,
        "doc_id": doc_id,
        "doc_sha": doc_sha,
        "client_id": client_id,
        "project_id": metadata.get("project_id"),
    }
    try:
        pub("®️ Registering file in the database...", **doc_ctx)
        update_doc_db(
            doc_id=doc_id,
            # Review the DocumentInfo model to ensure it matches your schema
            update=DBDocumentInfo(
                id=doc_id,
                sha1=doc_sha,
                name=doc_name,
                client_id=client_id,
                collection=collection_name,
                status=DOC_STATUS.PENDING.value,
                created_at=datetime.now().isoformat(),
                run_id=flow_run.id,
                metadata=metadata,
            ).model_dump(),
            upsert=True,
        )
        pub("📝 Indexing file...", **doc_ctx)
        inserted_nodes = index_file.submit(
            fpath=fpath,
            doc_id=doc_id,
            collection_name=collection_name,
            embedding_model_id=embedding_model_id,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            llm_backend=llm_backend,
            vector_store_backend=vector_store_backend,
            metadata=metadata,
        ).result()
        if inserted_nodes:
            pub(f"✅ Successfully indexed {inserted_nodes} nodes.", **doc_ctx)
        else:
            pub("⏎ Document already indexed, skipping...", **doc_ctx)
        update_doc_db(doc_id, {"status": DOC_STATUS.INDEXED.value})
    except Exception as e:
        pub(f"💥 Error processing '{doc_name}': {e}", **doc_ctx, level="error")
        update_doc_db(doc_id, {"status": DOC_STATUS.FAILED.value})
        raise


PUBLIC_FLOWS: dict[str, Flow] = {
    index_document_file.name: index_document_file,
}
