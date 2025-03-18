from hashlib import sha1
from pathlib import Path

from llama_index.core.schema import Document
from loguru import logger
from prefect import Flow, flow

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
    # From here should all be taken from settings and not passed around (env settings)
    chroma_host: str = settings.CHROMA_HOST,
    chroma_port: int = settings.CHROMA_PORT,
    redis_host: str | None = settings.REDIS_HOST,
    redis_port: int | None = settings.REDIS_PORT,
    ollama_base_url: str | None = settings.OLLAMA_BASE_URL,
    parser_base_url: str = settings.PDF_PARSER_BASE_URL,
    openai_api_key: str | None = None,
):
    """Index all the files in the data directory

    Args:
        client_id (str): Client ID
        file_paths (list[str]): List of file paths to index
        chroma_collection (str): Name of the collection to index the documents to
        chroma_host (str, optional): ChromaDB host. Defaults to settings.CHROMA_HOST.
        chroma_port (int, optional): ChromaDB port. Defaults to settings.CHROMA_PORT.
        metadatas (list[dict], optional): List of metadata dictionaries for each file. Defaults to [].
        llm_backend (str, optional): LLM backend to use. Defaults to settings.LLM_BACKEND.
        embedding_model (str, optional): Embedding model to use. Defaults to settings.EMBEDDING_MODEL.
        openai_api_key (str, optional): OpenAI API key. Defaults to settings.OPENAI_API_KEY.
        ollama_base_url (str, optional): Ollama base URL. Defaults to settings.OLLAMA_BASE_URL.
        parser_base_url (str, optional): Parser base URL. Defaults to settings.PDF_PARSER_BASE_URL.
        chunk_size (int, optional): Size of the chunks to split the documents into. Defaults to settings.CHUNK_SIZE.
        chunk_overlap (int, optional): Overlap between the chunks. Defaults to settings.CHUNK_OVERLAP.
        redis_host (str, optional): Redis host (used for broadcasting updated). Defaults to settings.REDIS_HOST.
        redis_port (int, optional): Redis port (used for broadcasting updated). Defaults to settings.REDIS_PORT.
    """
    from flows.common.clients.pubsub import UpdatePublisher
    from flows.preproc.convert import pdf_2_md
    from flows.preproc.index import index_documents

    if metadatas and len(metadatas) != len(file_paths):
        raise ValueError("⚠️ Length of metadatas should match the length of file_paths")

    if redis_host and redis_port:
        pub = UpdatePublisher(client_id, host=redis_host, port=redis_port)
    else:
        pub = None

    documents = []
    for i, fpath in enumerate(file_paths):
        fpath = Path(fpath)

        try:
            doc_id = sha1(fpath.open("rb").read()).hexdigest()
            if pub:
                pub.publish_update(f"Parsing {fpath.stem}...", doc_id=doc_id)

            # Read the file (possibly a PDF which will be converted to text)
            if fpath.suffix == ".pdf":
                text = pdf_2_md.submit(str(fpath), parser_base_url).result()
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
        #  Also env settings
        chroma_host=chroma_host,
        chroma_port=chroma_port,
        ollama_base_url=ollama_base_url,
        openai_api_key=openai_api_key,
    )


PUBLIC_FLOWS: dict[str, Flow] = {
    index_files.name: index_files,
}
