import os
from pathlib import Path
from typing import Any

from llama_index.core import Settings
from loguru import logger
from prefect import Flow, flow

from flows.shrag.constants import (
    CHROMA_HOST_DEFAULT,
    CHROMA_HOST_ENV_VAR,
    CHROMA_PORT_DEFAULT,
    CHROMA_PORT_ENV_VAR,
    EMBEDDING_MODEL_DEFAULT,
    EMBEDDING_MODEL_ENV_VAR,
    LLM_BACKEND_DEFAULT,
    LLM_BACKEND_ENV_VAR,
    LLM_MODEL_DEFAULT,
    LLM_MODEL_ENV_VAR,
    SIMILARITY_CUTOFF_DEFAULT,
    SIMILARITY_TOP_K_DEFAULT,
)


@flow(log_prints=True, flow_run_name="playbook-QA-{chroma_collection_name}-{llm_model}")
def playbook_qa(
    playbook_json: Path | str,
    meta_filters: dict[str, Any],
    chroma_collection_name: str,
    chroma_host: str = os.getenv(CHROMA_HOST_ENV_VAR, CHROMA_HOST_DEFAULT),
    chroma_port: int = os.getenv(CHROMA_PORT_ENV_VAR, CHROMA_PORT_DEFAULT),
    llm_backend: str = os.getenv(LLM_BACKEND_ENV_VAR, LLM_BACKEND_DEFAULT),
    llm_model: str = os.getenv(LLM_MODEL_ENV_VAR, LLM_MODEL_DEFAULT),
    embedding_model: str = os.getenv(EMBEDDING_MODEL_ENV_VAR, EMBEDDING_MODEL_DEFAULT),
    reranker_model: str | None = None,
    similarity_top_k: int = SIMILARITY_TOP_K_DEFAULT,
    similarity_cutoff: float = SIMILARITY_CUTOFF_DEFAULT,
):
    """This flow is responsible for performing Structured QA on a set of
    textual chunks retrieved from a vector DB based on metadata filtering.
    For this flow to work, the documents must have been pre-processed and present
    in the given chromaDB collection.

    Args:
        playbook_json (Path | str): Path to the playbook JSON file
        meta_filters (dict[str, Any], optional): Metadata filters for retrieval
            as {key:value} mapping. Leave as an empty dict for no filtering.
        chroma_collection_name (str): Name of the ChromaDB collection
        chroma_host (str, optional): ChromaDB host.
            Defaults to CHROMA_HOST_DEFAULT.
        chroma_port (int, optional): ChromaDB port.
            Defaults to CHROMA_PORT_DEFAULT.
        llm_backend (str, optional): LLM backend to use.
            Defaults to LLM_BACKEND_DEFAULT.
        llm_model (str, optional): LLM model to use.
            Defaults to LLM_MODEL_DEFAULT.
        embedding_model (str, optional): Embedding model to use.
            Defaults to EMBEDDING_MODEL_DEFAULT.
        reranker_model (str | None, optional): Reranker model to use.
            Defaults to None.
        similarity_top_k (int, optional): Number of top results to retrieve.
            Defaults to SIMILARITY_TOP_K_DEFAULT.
        similarity_cutoff (float, optional): Similarity cutoff for retrieval.
            Defaults to SIMILARITY_CUTOFF_DEFAULT.
    Returns:
        responses (list[QAResponse]): List of QAResponse objects containing the question, question type and answer
        for each question in the question library.
    """
    from flows.common.clients.chroma import ChromaClient
    from flows.common.clients.llms import get_embedding_model, get_llm
    from flows.shrag.playbook import build_question_library
    from flows.shrag.qa import QAgent

    # Build the Question Library
    q_collection = build_question_library(playbook_json)

    # Get the LLM and embedding model
    llm = get_llm(
        llm_backend=llm_backend,
        llm_model=llm_model,
    )
    embed_model = get_embedding_model(
        llm_backend=llm_backend, embedding_model=embedding_model
    )
    Settings.llm = llm
    Settings.embed_model = embed_model

    # Get the ChromaDB index
    index = ChromaClient(chroma_host, chroma_port).get_index(
        embed_model, chroma_collection_name
    )
    logger.info("🔍 Index loaded successfully!")

    # Init the QAgent
    questioner = QAgent(
        index=index,
        llm=llm,
        reranker=reranker_model,
    )

    # Run the Q-collection and return the responses
    responses = questioner.run_q_collection(
        q_collection=q_collection,
        meta_filters=meta_filters,
        similarity_top_k=similarity_top_k,
        similarity_cutoff=similarity_cutoff,
        pbar=True,
    )
    return {k: v.model_dump() for k, v in responses.items()}


PUBLIC_FLOWS: dict[str, Flow] = {
    playbook_qa.name: playbook_qa,
}
