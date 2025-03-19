from hashlib import sha1
from pathlib import Path

from llama_index.core.schema import Document
from loguru import logger
from prefect import Flow, flow

from flows.common.helpers import noop
from flows.common.helpers.auto_download import download_if_remote
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
    from flows.common.clients.pubsub import UpdatePublisher
    from flows.preproc.convert import pdf_2_md
    from flows.preproc.index import index_documents

    if metadatas and len(metadatas) != len(file_paths):
        raise ValueError("⚠️ Length of metadatas should match the length of file_paths")

    if pubsub:
        pub = UpdatePublisher(client_id)
    else:
        pub = noop

    documents = []
    for i, fpath in enumerate(file_paths):
        fpath = Path(fpath)

        try:
            doc_id = sha1(fpath.open("rb").read()).hexdigest()
            if pub:
                pub.publish_update(f"Parsing {fpath.stem}...", doc_id=doc_id)

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

    logger.info(f"📚 Gathered {len(documents)} documents for indexing.")
    return index_documents(
        documents,
        chroma_collection=chroma_collection,
        llm_backend=llm_backend,
        embedding_model=embedding_model,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        pub=pub,
    )


PUBLIC_FLOWS: dict[str, Flow] = {
    index_files.name: index_files,
}
