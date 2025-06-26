from typing import Any

from loguru import logger
from prefect import Flow, flow

from flows.common.clients.llms import get_embedding_model
from flows.common.clients.vector_stores import (
    get_default_vector_collection_name,
    get_vector_store,
)
from flows.settings import settings


@flow(log_prints=True)
def delete_document_embeddings(
    doc_id: str,
    client_id: str,
    vector_store_backend: str = settings.VECTOR_STORE_BACKEND,
    embedding_model_id: str = settings.EMBEDDING_MODEL,
    llm_backend: str = settings.LLM_BACKEND,
    collection_name: str | None = None,
    **kwargs: Any,
) -> None:
    """Delete all embeddings for a given document ID from the specified vector store.

    Args:
        doc_id (str): The document ID whose embeddings should be deleted.
        client_id (str): The client ID (used for collection naming).
        vector_store_backend (str, optional): Backend to use (mongo/chroma).
            Defaults to settings.VECTOR_STORE_BACKEND.
        embedding_model_id (str, optional): ID of the embedding model.
            Defaults to settings.EMBEDDING_MODEL.
        llm_backend (str, optional): LLM backend name.
            Defaults to settings.LLM_BACKEND.
        collection_name (str, optional): Name of the collection.
            If None, will be auto-determined.
        **kwargs: Additional arguments for the vector store client.
    """
    logger.info(
        f"🗑️ Deleting embeddings for doc_id={doc_id} "
        f"from vector store '{vector_store_backend}'..."
    )
    if collection_name is None:
        collection_name = get_default_vector_collection_name(
            vector_store_backend, client_id, llm_backend, embedding_model_id
        )
    embedding_model = get_embedding_model(embedding_model_id, llm_backend)
    vector_store = get_vector_store(vector_store_backend, embedding_model)
    vector_store.delete_doc(doc_id, collection_name)
    logger.info(
        f"✅ Embeddings for doc_id={doc_id} deleted from collection '{collection_name}'"
    )


PUBLIC_FLOWS: dict[str, Flow] = {
    delete_document_embeddings.name: delete_document_embeddings,
}
