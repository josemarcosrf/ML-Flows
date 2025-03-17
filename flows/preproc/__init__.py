from hashlib import sha1
from pathlib import Path

from llama_index.core.schema import Document
from loguru import logger
from prefect import Flow, flow

from flows.common.clients.pubsub import UpdatePublisher
from flows.common.helpers.auto_download import download_if_remote
from flows.preproc.convert import pdf_2_md
from flows.preproc.index import index_documents
from flows.settings import settings


@flow(log_prints=True, flow_run_name="Index Files={collection_name}")
@download_if_remote(include=["file_paths"])
def index_files(
    client_id: str,
    file_paths: list[str],
    collection_name: str,
    metadatas: list[dict] = [],
    embedding_model_name: str = settings.EMBEDDING_MODEL,
    llm_backend: str = settings.LLM_BACKEND,
    openai_api_key: str = settings.OPENAI_API_KEY,
    chunk_size: int = settings.CHUNK_SIZE,
    chunk_overlap: int = settings.CHUNK_OVERLAP,
    ollama_base_url: str = settings.OLLAMA_BASE_URL,
    parser_base_url: str = settings.PDF_PARSER_BASE_URL,
    chroma_host: str = settings.CHROMA_HOST,
    chroma_port: int = settings.CHROMA_PORT,
    redis_host: str = settings.REDIS_HOST,
    redis_port: int = settings.REDIS_PORT,
):
    """Index all the files in the data directory"""

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
                pub.publish_update(doc_id, {"message": f"Parsing {fpath.stem}..."})

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
    index_documents(
        documents,
        collection_name=collection_name,
        llm_backend=llm_backend,
        embedding_model_name=embedding_model_name,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        chroma_host=chroma_host,
        chroma_port=chroma_port,
        ollama_base_url=ollama_base_url,
        openai_api_key=openai_api_key,
        pub=pub,
    )


PUBLIC_FLOWS: dict[str, Flow] = {
    index_files.name: index_files,
}
