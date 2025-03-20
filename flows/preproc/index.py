from pathlib import Path

from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document
from prefect import task

from flows.common.clients.chroma import ChromaClient
from flows.common.clients.llms import get_embedding_model
from flows.preproc.convert import pdf_2_md


def custom_task_run_name() -> str:
    from prefect.runtime import task_run

    function_name = task_run.get_task_name()
    parameters = task_run.get_parameters()
    fname = Path(parameters.get("fpath", "")).stem
    return f"{function_name}={fname}"


@task(log_prints=True, task_run_name=custom_task_run_name)
def index_file(
    fpath: str,
    doc_id: str,
    llm_backend: str,
    embedding_model: str,
    chunk_size: int,
    chunk_overlap: int,
    chroma_collection: str,
    metadata: dict = {},
) -> int:
    """Index a single file in ChromaDB.

    Args:
        fpath (Path): Path to the file to index
        doc_id (str): Document ID
        chroma_collection (str): Name of the collection to index the documents to
        llm_backend (str): LLM backend to use. One of openai, ollama
        embedding_model (str): Embedding model to use.
        chunk_size (int): Size of the chunks to split the documents into
        chunk_overlap (int): Overlap between the chunks

    Returns:
        int: The Number of nodes inserted
    """
    # Read the file (OCR or otherwise)
    if fpath.suffix == ".pdf":
        text = pdf_2_md.submit(str(fpath)).result()
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
        chroma_collection=chroma_collection,
        llm_backend=llm_backend,
        embedding_model=embedding_model,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    ).result()


@task
def index_document(
    doc: Document,
    llm_backend: str,
    embedding_model: str,
    chunk_size: int,
    chunk_overlap: int,
    chroma_collection: str,
) -> int:
    """Index a single document in ChromaDB.

    Args:
        docs (Document): Document object to index
        chroma_collection (str): Name of the collection to index the documents to
        llm_backend (str): LLM backend to use. One of openai, ollama
        embedding_model (str): Embedding model to use.
        chunk_size (int): Size of the chunks to split the documents into
        chunk_overlap (int): Overlap between the chunks

    Returns:
        int: Number of nodes inserted
    """
    # Connect to ChromaDB and get the embedding function
    vec_db = ChromaClient()
    embed_fn = vec_db.get_embedding_function(embedding_model, llm_backend)

    # Get or create the chromaDB collection
    col = vec_db.get_collection(
        chroma_collection,
        embed_fn=embed_fn,
        create=True,
    )
    embed_model = get_embedding_model(embedding_model, llm_backend)
    index = vec_db.get_index(embed_model, chroma_collection)

    # Insertion pipeline
    pipeline = IngestionPipeline(
        transformations=[
            SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap),
            embed_model,
        ]
    )
    existing_nodes = col.get(where={"doc_id": doc.doc_id})
    if existing_nodes["ids"]:
        return 0

    nodes = pipeline.run(documents=[doc])  # Run the pre-proc pipeline
    index.insert_nodes(nodes)

    return len(nodes)
