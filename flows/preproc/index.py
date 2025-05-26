from pathlib import Path

from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document
from loguru import logger
from prefect import task

from flows.common.clients.llms import get_embedding_model
from flows.common.clients.vector_stores import get_vector_store
from flows.preproc.convert import docling_2_md


def custom_task_run_name() -> str:
    from prefect.runtime import task_run

    function_name = task_run.get_task_name()
    parameters = task_run.get_parameters()
    fname = Path(parameters.get("fpath", "")).stem
    return f"{function_name}={fname}"


@task(log_prints=True, task_run_name=custom_task_run_name)
def index_file(
    fpath: Path,
    doc_id: str,
    vector_store_backend: str,
    llm_backend: str,
    embedding_model: str,
    chunk_size: int,
    chunk_overlap: int,
    metadata: dict = {},
) -> int:
    """Index a single file in ChromaDB.

    Args:
        fpath (Path): Path to the file to index
        doc_id (str): Document ID
        vector_store_backend (str): Vector store backend to use. One of chroma, mongo
        llm_backend (str): LLM backend to use. One of openai, ollama
        embedding_model (str): Embedding model to use.
        chunk_size (int): Size of the chunks to split the documents into
        chunk_overlap (int): Overlap between the chunks

    Returns:
        int: The Number of nodes inserted
    """
    # Read the file (OCR or otherwise)
    if fpath.suffix == ".pdf":
        text = docling_2_md.submit(str(fpath)).result()
    else:
        with fpath.open("r") as f:
            text = f.read()

    # Create a document object
    doc = Document(
        doc_id=doc_id,  # Use the SHA1 hash of the PDF file as the ID
        text=text,
        extra_info={
            "name": fpath.stem,
            **metadata,
        },
    )
    # Index the document
    return index_document.submit(
        doc=doc,
        vector_store_backend=vector_store_backend,
        llm_backend=llm_backend,
        embedding_model=embedding_model,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    ).result()


@task
def index_document(
    doc: Document,
    vector_store_backend: str,
    llm_backend: str,
    embedding_model: str,
    chunk_size: int,
    chunk_overlap: int,
) -> int:
    """Index a single document in ChromaDB. This task is responsible for splitting the
    document into chunks, embedding the chunks, and inserting them into the
    ChromaDB collection.

    Args:
        docs (Document): Document object to index
        vector_store_backend (str): Vector store backend to use. One of chroma, mongo
        llm_backend (str): LLM backend to use. One of openai, ollama
        embedding_model (str): Embedding model to use.
        chunk_size (int): Size of the chunks to split the documents into
        chunk_overlap (int): Overlap between the chunks

    Returns:
        int: Number of nodes inserted
    """

    # Get the embedding model and connect to the VectorStore
    embed_model = get_embedding_model(embedding_model, llm_backend)
    store = get_vector_store(vector_store_backend, embed_model)

    # Insertion pipeline
    pipeline = IngestionPipeline(
        transformations=[
            SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap),
            embed_model,
        ]
    )

    # Get the index from the vector store
    if not store.index_exists():
        index = store.create_index()
    else:
        index = store.get_index()

    if existing_nodes := store.get_doc(doc.doc_id):
        logger.info(
            f"Found {len(existing_nodes)} for document {doc.doc_id}. Skipping indexing."
        )
        return 0
    else:
        nodes = pipeline.run(documents=[doc])  # Run the pre-proc pipeline
        index.insert_nodes(nodes)

        return len(nodes)
