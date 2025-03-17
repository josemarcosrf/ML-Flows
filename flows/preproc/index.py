from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document
from loguru import logger
from prefect import task
from tqdm import tqdm

from flows.common.clients.chroma import ChromaClient
from flows.common.clients.llms import get_embedding_model
from flows.common.clients.pubsub import UpdatePublisher


@task
def index_documents(
    docs: list[Document],
    llm_backend: str,
    embedding_model: str,
    chunk_size: int,
    chunk_overlap: int,
    chroma_collection: str,
    chroma_host: str,
    chroma_port: int,
    ollama_base_url: str | None = None,
    openai_api_key: str | None = None,
    pub: UpdatePublisher | None = None,
):
    """Index a list of documents in ChromaDB

    Args:
        docs (list[Document]): List of documents to index
        chroma_collection (str): Name of the collection to index the documents to
        llm_backend (str): LLM backend to use. One of openai, ollama
        embedding_model (str): Embedding model to use.
        chunk_size (int): Size of the chunks to split the documents into
        chunk_overlap (int): Overlap between the chunks
        chroma_host (str): ChromaDB host
        chroma_port (int): Chroma
    """

    # Connect to ChromaDB and get the embedding function
    vec_db = ChromaClient(chroma_host, chroma_port)
    embed_fn = vec_db.get_embedding_function(
        llm_backend, embedding_model, ollama_base_url, openai_api_key
    )
    # Get or create the chromaDB collection
    col = vec_db.get_collection(
        chroma_collection,
        embed_fn=embed_fn,
        create=True,
    )
    # Get the Vector Index
    embed_model = get_embedding_model(
        llm_backend,
        embedding_model,
        ollama_base_url=ollama_base_url,
        openai_api_key=openai_api_key,
    )
    index = vec_db.get_index(embed_model, chroma_collection)

    # Insertion pipeline
    pipeline = IngestionPipeline(
        transformations=[
            SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap),
            embed_model,
        ]
    )
    # TODO: This for loop can be parallelized refactoring into a Prefect task
    # Pre-process and index one by one so we are able to check if the document
    # already exists in the index
    logger.info(f"📦 Indexing {len(docs)} documents...")
    total_inserted = 0
    total_skipped = 0
    doc_iter = tqdm(docs)
    for doc in doc_iter:
        doc_name = doc.metadata["name"]
        doc_id = doc.doc_id
        # Add to the document metadata the LLM backend and model
        existing_nodes = col.get(where={"name": doc_name})
        if existing_nodes["ids"]:
            msg = f"✅ Found document '{doc_name}'. Skipping..."
            tqdm.write(msg)
            if pub:
                pub.publish_update(msg, doc_id=doc_id)
            total_skipped += 1
        else:
            msg = f"📩 Inserting '{doc_name}'"
            tqdm.write(msg)
            if pub:
                pub.publish_update(msg, doc_id=doc_id)
            nodes = pipeline.run(documents=[doc])  # Run the pre-proc pipeline
            index.insert_nodes(nodes)
            total_inserted += 1

    logger.info(f"Total inserted: {total_inserted} | Total skipped: {total_skipped}")
