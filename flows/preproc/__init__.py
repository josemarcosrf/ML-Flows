from datetime import datetime
from hashlib import sha1
from pathlib import Path

from loguru import logger
from prefect import Flow, flow

from flows.common.clients.mongo import MongoDBClient
from flows.common.clients.vector_stores import get_default_vector_collection_name
from flows.common.helpers import pub_and_log
from flows.common.helpers.auto_download import download_if_remote
from flows.common.types import DOC_STATUS, DocumentInfo
from flows.settings import settings


def custom_index_flow_run_name() -> str:
    """Generate a custom flow run name for indexing files"""
    from prefect.runtime import flow_run

    # function_name = flow_run.get_flow_name()
    parameters = flow_run.get_parameters()

    client_id = parameters.get("client_id", "unknown")
    vector_store_backend = parameters.get("vector_store_backend", "unknown")
    n_files = len(parameters.get("file_paths", []))

    return f"Index {n_files} files for {client_id} ({vector_store_backend})"


@flow(
    log_prints=True,
    flow_run_name=custom_index_flow_run_name,
)
@download_if_remote(include=["file_paths"])
def index_files(
    client_id: str,
    file_paths: list[str],
    embedding_model: str = settings.EMBEDDING_MODEL,
    chunk_size: int = settings.CHUNK_SIZE,
    chunk_overlap: int = settings.CHUNK_OVERLAP,
    llm_backend: str = settings.LLM_BACKEND,
    vector_store_backend: str = settings.VECTOR_STORE_BACKEND,
    pubsub: bool = False,
    metadatas: list[dict] = [],
):
    """Index all the files in the data directory

    Args:
        client_id (str): Client ID
        file_paths (list[str]): List of file paths to index
        embedding_model (str, optional): Embedding model to use.
        chunk_size (int, optional): Size of the chunks to split the documents into.
        chunk_overlap (int, optional): Overlap between the chunks.
        llm_backend (str, optional): LLM backend to use.
        vector_store_backend (str, optional): Vector store backend to use.
        pubsub (bool, optional): Whether to use Pub/Sub for updates.
            Defaults to False.
        metadatas (list[dict], optional): List of metadata dictionaries for each file.
    """
    from flows.preproc.index import index_file

    # Define a function to update the document in the MongoDB collection
    def update_doc_db(doc_id: str, update: dict, upsert=False):
        res = db.update_one(
            settings.MONGO_DOC_COLLECTION,
            filter={"id": doc_id},
            update=update,
            upsert=upsert,
        )
        logger.debug(f"DB update results: {res}")

    if metadatas:
        if len(metadatas) != len(file_paths):
            raise ValueError(
                "⚠️ Length of metadatas should match the length of file_paths"
            )

        for i in range(len(metadatas)):
            metadatas[i].update({"client_id": client_id})
    else:
        metadatas = [{"client_id": client_id} for _ in file_paths]

    # Define a pubsub function that combine the logger and the publisher
    pub = pub_and_log(client_id, pubsub)

    # Connect to MongoDB
    db = MongoDBClient()

    pub(f"Reading {len(file_paths)} files...")
    full_paths = [Path(fp).resolve() for fp in file_paths]
    doc_ids = [sha1(fpath.open("rb").read()).hexdigest() for fpath in full_paths]

    pub(f"📚 Gathered {len(file_paths)} documents for indexing.")
    total_inserted = 0
    total_skipped = 0
    total_errors = 0
    tasks = []

    collection_name = get_default_vector_collection_name(
        vector_store_backend=vector_store_backend,
        client_id=client_id,
        llm_backend=llm_backend,
        embedding_model=embedding_model,
    )

    for i, (fpath, doc_id) in enumerate(zip(full_paths, doc_ids)):
        # Launch the indexing tasks
        try:
            pub(
                "®️ Registering file in the database...",
                doc_name=fpath.stem,
                doc_id=doc_id,
            )
            # Insert the document metadata into the MongoDB collection
            update_doc_db(
                doc_id,
                DocumentInfo(
                    id=doc_id,
                    name=fpath.stem,
                    client_id=client_id,
                    collection=collection_name,
                    status=DOC_STATUS.PENDING.value,
                    created_at=datetime.now().isoformat(),
                ).model_dump(),
                upsert=True,
            )

            # Read the file (possibly a PDF which will be converted to text)
            pub("📝 Indexing file...", doc_name=fpath.stem, doc_id=doc_id)
            future = index_file.submit(
                fpath=fpath,
                doc_id=doc_id,
                collection_name=collection_name,
                vector_store_backend=vector_store_backend,
                llm_backend=llm_backend,
                embedding_model=embedding_model,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                metadata=metadatas[i] if metadatas else {},
            )
            logger.debug(f"Task {future} submitted for {fpath.name}")
            tasks.append(future)
        except Exception as e:
            pub(f"💥 Error processing '{fpath.name}': {e}", level="error")
            update_doc_db(doc_id, {"status": DOC_STATUS.FAILED.value})
            total_errors += 1

        # Wait for completion of the tasks
        for task in tasks:
            try:
                if inserted_nodes := task.result():
                    pub(
                        f"✅ Successfully indexed {inserted_nodes} nodes.",
                        doc_name=fpath.stem,
                        doc_id=doc_id,
                    )
                    total_inserted += 1
                else:
                    pub(
                        "⏎ Document already indexed, skipping...",
                        doc_name=fpath.stem,
                        doc_id=doc_id,
                    )
                    total_skipped += 1
            except Exception as e:
                pub(f"💥 Error inserting '{fpath.name}': {e}", level="error")
                update_doc_db(doc_id, {"status": DOC_STATUS.FAILED.value})
                total_errors += 1
            else:
                update_doc_db(doc_id, {"status": DOC_STATUS.INDEXED.value})

    stats = {
        "inserted": total_inserted,
        "skipped": total_skipped,
        "errors": total_errors,
    }
    pub("Indexing completed!", extra=stats)

    if total_errors > 0:
        raise RuntimeError(f"Errors occurred during indexing: {total_errors}")


PUBLIC_FLOWS: dict[str, Flow] = {
    index_files.name: index_files,
}
