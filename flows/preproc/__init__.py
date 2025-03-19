from hashlib import sha1
from pathlib import Path

from llama_index.core.schema import Document
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

    from flows.preproc.convert import pdf_2_md
    from flows.preproc.index import index_documents

    if metadatas and len(metadatas) != len(file_paths):
        raise ValueError("⚠️ Length of metadatas should match the length of file_paths")

    # Combine the logger and the publisher
    pub = pub_and_log(client_id, pubsub)

    pub(f"Reading {len(file_paths)} files...")
    file_paths = [Path(fp).resolve() for fp in file_paths]
    doc_ids = [sha1(fpath.open("rb").read()).hexdigest() for fpath in file_paths]

    # Insert the documents into the MongoDB collection for bookkeeping
    db_data = [
        DocumentInfo(
            client_id=client_id,
            collection=chroma_collection,
            name=f.stem,
            doc_id=doc_id,
            status=DOC_STATUS.PENDING.value,
        ).model_dump()
        for f, doc_id in zip(file_paths, doc_ids)
    ]
    MongoDBClient().insert_many(settings.MONGO_DOC_COLLECTION, db_data)

    documents = []
    for i, (fpath, doc_id) in enumerate(zip(file_paths, doc_ids)):
        try:
            pub("Parsing document...", doc_name=fpath.stem, doc_id=doc_id)

            # Read the file (possibly a PDF which will be converted to text)
            if fpath.suffix == ".pdf":
                text = pdf_2_md.submit(str(fpath)).result()
            else:
                with fpath.open("r") as f:
                    text = f.read()

            # Create a list documents
            doc_meta = metadatas[i] if metadatas else {}
            documents.append(
                Document(
                    doc_id=doc_id,  # Use the SHA1 hash of the PDF file as the ID
                    text=text,
                    extra_info={
                        "name": fpath.stem,
                        **doc_meta,
                    },
                )
            )
        except Exception as e:
            logger.error(f"💥 Error processing {fpath.name}: {e}")
            continue

    pub(f"📚 Gathered {len(documents)} documents for indexing.")
    return index_documents(
        documents,
        chroma_collection=chroma_collection,
        llm_backend=llm_backend,
        embedding_model=embedding_model,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        ctx={"client_id": client_id, "pubsub": pubsub},
    )


PUBLIC_FLOWS: dict[str, Flow] = {
    index_files.name: index_files,
}
