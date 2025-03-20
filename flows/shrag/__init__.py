from typing import Any

from llama_index.core import Settings
from loguru import logger
from prefect import Flow, flow

from flows.common.helpers import pub_and_log
from flows.common.types import ClientContext
from flows.settings import settings


@flow(
    log_prints=True,
    flow_run_name="playbook-QA-{chroma_collection}-{llm_model}-{meta_filters}",
)
def playbook_qa(
    client_id: str,
    playbook: dict[str, dict[str, str | list[str]]],
    meta_filters: dict[str, Any],
    chroma_collection: str,
    embedding_model: str = settings.EMBEDDING_MODEL,
    reranker_model: str | None = None,
    similarity_top_k: int = settings.SIMILARITY_TOP_K,
    similarity_cutoff: float = settings.SIMILARITY_CUTOFF,
    llm_backend: str = settings.LLM_BACKEND,
    llm_model: str = settings.LLM_MODEL,
    pubsub: bool = False,
):
    """Perform Structured RAG-QA on a set of textual chunks retrieved from a vector DB
    based on metadata filtering. For this flow to work, the documents must have
    been pre-processed and present in the given chromaDB collection.

    Args:
        client_id (str): Client ID for the Pub/Sub updates
        playbook (str): Mapping with 'id','name' and 'defintion' keys.
            The definition key contains the question library with each item having:
            'question', 'question_type' and 'valid_answers' for each attribute
        meta_filters (dict[str, Any], optional): Metadata filters for retrieval
            as {key:value} mapping. Leave as an empty dict for no filtering.
        chroma_collection (str): Name of the ChromaDB collection
        embedding_model (str, optional): Embedding model to use.
            Defaults to EMBEDDING_MODEL_DEFAULT.
        reranker_model (str | None, optional): Reranker model to use.
            Defaults to None.
        similarity_top_k (int, optional): Number of top results to retrieve.
            Defaults to SIMILARITY_TOP_K_DEFAULT.
        similarity_cutoff (float, optional): Similarity cutoff for retrieval.
            Defaults to SIMILARITY_CUTOFF_DEFAULT.
        llm_backend (str, optional): LLM backend to use.
            Defaults to LLM_BACKEND_DEFAULT.
        llm_model (str, optional): LLM model to use.
            Defaults to LLM_MODEL_DEFAULT.
        pubsub (bool, optional): Whether to use Pub/Sub for updates.
            Defaults to False.
    Returns:
        responses (list[QAResponse]): List of QAResponse objects containing the question, question type and answer
        for each question in the question library.
    """
    from flows.common.clients.chroma import ChromaClient
    from flows.common.clients.llms import get_embedding_model, get_llm
    from flows.shrag.playbook import build_question_library
    from flows.shrag.qa import QAgent

    # Combine the logger and the publisher
    pub = pub_and_log(client_id, pubsub)

    # Get the LLM and embedding model
    llm = get_llm(llm_model=llm_model, llm_backend=llm_backend)
    embed_model = get_embedding_model(
        llm_backend=llm_backend, embedding_model=embedding_model
    )
    Settings.llm = llm
    Settings.embed_model = embed_model

    # Get the ChromaDB index
    index = ChromaClient().get_index(embed_model, chroma_collection)
    logger.info("🔍 Index loaded successfully!")

    # Init the QAgent
    pub("🤖 Initializing QAgent...")
    questioner = QAgent(
        index=index,
        llm=llm,
        reranker=reranker_model,
    )
    # Build a flow context
    ctx = ClientContext(
        client_id=client_id,
        meta_filters=meta_filters,
        collection=chroma_collection,
        playbook_id=playbook["id"],
        pub=True,
    )
    # Build the Question Library
    pub(f"📚 Building question library for playbook {playbook['name']}")
    q_collection = build_question_library(playbook["definitions"])

    # Run the Q-collection and return the responses
    responses = questioner.run_q_collection(
        q_collection=q_collection,
        meta_filters=meta_filters,
        similarity_top_k=similarity_top_k,
        similarity_cutoff=similarity_cutoff,
        pbar=False,
        ctx=ctx,
    )

    return {k: v.model_dump() for k, v in responses.items()}


PUBLIC_FLOWS: dict[str, Flow] = {
    playbook_qa.name: playbook_qa,
}
