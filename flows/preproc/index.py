from pathlib import Path

from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document
from loguru import logger
from prefect import task

from flows.common.clients.llms import get_embedding_model
from flows.common.clients.vector_stores import get_vector_store
from flows.preproc.convert import docling_2_md


def custom_index_task_run_name() -> str:
    from prefect.runtime import task_run

    function_name = task_run.get_task_name()
    parameters = task_run.get_parameters()
    fname = Path(parameters.get("fpath", "")).stem
    return f"{function_name}={fname}"


@task(
    log_prints=True,
    task_run_name=custom_index_task_run_name,
)
def index_file(
    fpath: Path,
    doc_id: str,
    collection_name: str,
    embedding_model_id: str,
    chunk_size: int,
    chunk_overlap: int,
    llm_backend: str,
    vector_store_backend: str,
    metadata: dict | None = None,
) -> int:
    """Index a single file in ChromaDB.

    Args:
        fpath (Path): Path to the file to index
        doc_id (str): Document ID
        vector_store_backend (str): Vector store backend to use. One of chroma, mongo
        llm_backend (str): LLM backend to use. One of openai, ollama
        embedding_model_id (str): ID of the embedding model to use.
        chunk_size (int): Size of the chunks to split the documents into
        chunk_overlap (int): Overlap between the chunks

    Returns:
        int: The Number of nodes inserted
    """
    if metadata is None:
        metadata = {}

    # Read the file (OCR or otherwise)
    if fpath.suffix == ".pdf":
        text = docling_2_md.submit(str(fpath)).result()
    else:
        with fpath.open("r") as f:
            text = f.read()

    # Create a document object
    doc_name = metadata.get("name", fpath.stem)
    doc = Document(
        doc_id=doc_id,  # Use the SHA1 hash of the file as the ID
        text=text,
        extra_info={
            "name": doc_name,
            "llm_backend": llm_backend,
            "vector_store_backend": vector_store_backend,
            "embedding_model": embedding_model_id,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            **metadata,
        },
    )
    # Index the document
    return index_document.submit(
        doc=doc,
        collection_name=collection_name,
        embedding_model_id=embedding_model_id,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        llm_backend=llm_backend,
        vector_store_backend=vector_store_backend,
    ).result()


@task
def index_document(
    doc: Document,
    collection_name: str,
    embedding_model_id: str,
    chunk_size: int,
    chunk_overlap: int,
    llm_backend: str,
    vector_store_backend: str,
) -> int:
    """Index a single document.
    This task is responsible for splitting the document into chunks,
    embedding the chunks, and inserting them into the vector store.

    Args:
        docs (Document): Document object to index
        collection_name (str): Name of the collection to insert the document into
        vector_store_backend (str): Vector store backend to use. One of chroma, mongo
        llm_backend (str): LLM backend to use. One of openai, ollama
        embedding_model_id (str): ID of the embedding model to use.
        chunk_size (int): Size of the chunks to split the documents into
        chunk_overlap (int): Overlap between the chunks

    Returns:
        int: Number of nodes inserted
    """
    logger.info(f"Indexing document {doc.doc_id} with {len(doc.text)} characters.")
    logger.info(
        f"Using collection '{collection_name}' "
        f"with vector store backend '{vector_store_backend}' "
        f"and LLM backend '{llm_backend}' (model={embedding_model_id})."
    )
    # Get the embedding model and connect to the VectorStore
    embedding_model = get_embedding_model(embedding_model_id, llm_backend)
    vec_store = get_vector_store(vector_store_backend, embedding_model)

    # Insertion pipeline
    pipeline = IngestionPipeline(
        transformations=[
            SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap),
            embedding_model,
        ]
    )

    # Get the index from the vector store
    index = vec_store.get_index(
        collection_name,
        create_if_not_exists=True,
        index_filters=[f"metadata.{field}" for field in doc.metadata.keys()],
    )

    if existing_nodes := vec_store.get_docs(
        doc.doc_id, collection_name=collection_name
    ):
        logger.info(
            f"Found {len(existing_nodes)} for document {doc.doc_id}. Skipping indexing."
        )
        return 0
    else:
        nodes = pipeline.run(documents=[doc])  # Run the pre-proc pipeline
        index.insert_nodes(nodes)

        return len(nodes)
