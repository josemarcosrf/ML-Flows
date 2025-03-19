from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document
from loguru import logger
from prefect import task

from flows.common.clients.chroma import ChromaClient
from flows.common.clients.llms import get_embedding_model
from flows.common.clients.mongodb import MongoDBClient
from flows.common.helpers import noop, pub_and_log
from flows.common.types import DOC_STATUS
from flows.settings import settings


@task
def index_documents(
    docs: list[Document],
    llm_backend: str,
    embedding_model: str,
    chunk_size: int,
    chunk_overlap: int,
    chroma_collection: str,
    ctx: dict | None = None,
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
        ctx (dict, optional): Prefect parent Flow context. Defaults to None.
    """

    # Define a function to update the document in the MongoDB collection
    def update_doc_db(doc, udpate):
        res = db.update_one(
            settings.MONGO_DOC_COLLECTION,
            filter={"doc_id": doc.doc_id},
            update=udpate,
            upsert=False,
        )
        logger.debug(f"Update results: {res}")

    # Connect to MongoDB
    db = MongoDBClient()

    # Define a pubsub function
    pub = pub_and_log(**ctx) if ctx else noop

    # Connect to ChromaDB and get the embedding function
    vec_db = ChromaClient()
    embed_fn = vec_db.get_embedding_function(embedding_model, llm_backend)

    # Get or create the chromaDB collection
    col = vec_db.get_collection(
        chroma_collection,
        embed_fn=embed_fn,
        create=True,
    )
    # Get the Vector Index
    embed_model = get_embedding_model(embedding_model, llm_backend)
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
    pub(f"📦 Indexing {len(docs)} documents...")
    total_inserted = 0
    total_skipped = 0
    total_errors = 0
    for doc in docs:
        doc_name = doc.metadata["name"]
        doc_id = doc.doc_id
        update_doc_db(doc, {"status": DOC_STATUS.INDEXING.value})
        try:
            existing_nodes = col.get(where={"name": doc_name})
            if existing_nodes["ids"]:
                pub(f"✅ Found document '{doc_name}'. Skipping...", doc_id=doc_id)
                total_skipped += 1
            else:
                pub(f"📩 Inserting '{doc_name}'", doc_id=doc_id)
                nodes = pipeline.run(documents=[doc])  # Run the pre-proc pipeline
                index.insert_nodes(nodes)
                total_inserted += 1
        except Exception as e:
            msg = f"❌ Error inserting '{doc_name}': {e}"
            pub(msg, doc_id=doc_id, level="error")
            update_doc_db(doc, {"status": DOC_STATUS.FAILED.value, "reason": str(e)})
            total_errors += 1
        finally:
            update_doc_db(doc, {"status": DOC_STATUS.INDEXED.value})

    pub("✅ Indexing complete!")
    pub(f"Inserted:{total_inserted} | Skipped:{total_skipped} | Errors:{total_errors}")

    return {
        "inserted": total_inserted,
        "skipped": total_skipped,
        "errors": total_errors,
    }
