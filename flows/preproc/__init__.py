from hashlib import sha1
from pathlib import Path

from llama_index.core.schema import Document
from loguru import logger
from prefect import Flow, flow

from flows.common.helpers.auto_download import download_if_remote
from flows.preproc.convert import pdf_2_md
from flows.preproc.index import index_documents
from flows.settings import settings


@flow(log_prints=True, flow_run_name="Index Files={collection_name}")
@download_if_remote
def index_files(
    file_paths: list[str],
    collection_name: str,
    metadatas: list[dict] = [],
    llm_backend: str = settings.LLM_BACKEND,
    embedding_model_name: str = settings.EMBEDDING_MODEL,
    chunk_size: int = settings.CHUNK_SIZE,
    chunk_overlap: int = settings.CHUNK_OVERLAP,
    chroma_host: str = settings.CHROMA_HOST,
    chroma_port: int = settings.CHROMA_PORT,
):
    """Index all the files in the data directory"""

    if metadatas and len(metadatas) != len(file_paths):
        raise ValueError("⚠️ Length of metadatas should match the length of file_paths")

    documents = []
    for i, fpath in enumerate(file_paths):
        fpath = Path(fpath)

        try:
            # Read the file (possibly a PDF which will be converted to text)
            if fpath.suffix == ".pdf":
                text = pdf_2_md.submit(str(fpath)).result()
            else:
                with fpath.open("r") as f:
                    text = f.read()

            # Create a list documents
            doc_id = sha1(fpath.open("rb").read()).hexdigest()
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
    )


PUBLIC_FLOWS: dict[str, Flow] = {
    index_files.name: index_files,
}
