from datetime import datetime
from hashlib import sha1
from pathlib import Path

from loguru import logger
from prefect import Flow, flow

from flows.common.clients.mongodb import MongoDBClient
from flows.common.helpers import pub_and_log
from flows.common.helpers.auto_download import download_if_remote
from flows.common.types import DOC_STATUS, DocumentInfo
from flows.settings import settings


@flow(log_prints=True, flow_run_name="Index Files={chroma_collection}")
@download_if_remote(include=["file_paths"])
def index_files(
    client_id: str,
    file_paths: list[str],
    chroma_collection: str,
    metadatas: list[dict] = [],
    llm_backend: str = settings.LLM_BACKEND,
    embedding_model: str = settings.EMBEDDING_MODEL,
    chunk_size: int = settings.CHUNK_SIZE,
    chunk_overlap: int = settings.CHUNK_OVERLAP,
    pubsub: bool = False,
):
    """Index all the files in the data directory

    Args:
        client_id (str): Client ID
        file_paths (list[str]): List of file paths to index
        chroma_collection (str): Name of the collection to index the documents to
        metadatas (list[dict], optional): List of metadata dictionaries for each file. Defaults to [].
        llm_backend (str, optional): LLM backend to use. Defaults to settings.LLM_BACKEND.
        embedding_model (str, optional): Embedding model to use. Defaults to settings.EMBEDDING_MODEL.
        chunk_size (int, optional): Size of the chunks to split the documents into. Defaults to settings.CHUNK_SIZE.
        chunk_overlap (int, optional): Overlap between the chunks. Defaults to settings.CHUNK_OVERLAP.
        pubsub (bool, optional): Whether to use Pub/Sub for updates. Defaults to False.
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

    if metadatas and len(metadatas) != len(file_paths):
        raise ValueError("⚠️ Length of metadatas should match the length of file_paths")

    # Define a pubsub function that combine the logger and the publisher
    pub = pub_and_log(client_id, pubsub)

    # Connect to MongoDB
    db = MongoDBClient()

    pub(f"Reading {len(file_paths)} files...")
    file_paths = [Path(fp).resolve() for fp in file_paths]
    doc_ids = [sha1(fpath.open("rb").read()).hexdigest() for fpath in file_paths]

    pub(f"📚 Gathered {len(file_paths)} documents for indexing.")
    total_inserted = 0
    total_skipped = 0
    total_errors = 0
    tasks = []
    for i, (fpath, doc_id) in enumerate(zip(file_paths, doc_ids)):
        # Laucnh the indexing tasks
        try:
            pub("®️ Registering file...", doc_name=fpath.stem, doc_id=doc_id)
            # Insert the document metadata into the MongoDB collection
            update_doc_db(
                doc_id,
                DocumentInfo(
                    id=doc_id,
                    name=fpath.stem,
                    client_id=client_id,
                    collection=chroma_collection,
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
                llm_backend=llm_backend,
                embedding_model=embedding_model,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                chroma_collection=chroma_collection,
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
    pub("Indexing completed!", **stats)

    if total_errors > 0:
        raise RuntimeError(f"Errors occurred during indexing: {total_errors}")


PUBLIC_FLOWS: dict[str, Flow] = {
    index_files.name: index_files,
}
