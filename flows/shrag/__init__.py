from datetime import datetime as dt
from typing import Any

from loguru import logger
from prefect import Flow, flow, task
from prefect.runtime import flow_run

from flows.common.clients.mongo import MongoDBClient
from flows.common.clients.vector_stores import get_default_vector_collection_name
from flows.common.helpers import pub_and_log
from flows.common.types import Playbook
from flows.settings import settings


def playbook_qa_flow_run_name() -> str:
    func_name = flow_run.get_flow_name()
    parameters = flow_run.get_parameters()
    playbook_name = parameters["playbook"].name
    llm_name = parameters["llm_id"]
    return f"{func_name}-{playbook_name}-{llm_name}"


@flow(
    log_prints=True,
    flow_run_name=playbook_qa_flow_run_name,
)
def run_qa_playbook(
    client_id: str,
    playbook: Playbook,
    meta_filters: dict[str, Any] | None = None,
    llm_backend: str = settings.LLM_BACKEND,
    llm_id: str = settings.LLM_MODEL,
    embedding_model_id: str = settings.EMBEDDING_MODEL,
    reranker_model_id: str | None = None,
    similarity_top_k: int = settings.SIMILARITY_TOP_K,
    similarity_cutoff: float = settings.SIMILARITY_CUTOFF,
    vector_store_backend: str = settings.VECTOR_STORE_BACKEND,
    pubsub: bool = False,
):
    """Perform Structured RAG-QA on a set of textual chunks retrieved from a vector DB
    based on metadata filtering. For this flow to work, the documents must have
    been pre-processed and present in the given chromaDB collection.

    Args:
        client_id (str): external ID of the client, used to identify the
            documents and results in the MongoDB collection.
        playbook (str): Mapping with 'id','name' and 'defintion' keys.
            The definition key contains the question library with each item having:
            'question', 'question_type' and 'valid_answers' for each attribute
        meta_filters (dict[str, Any], optional): Metadata filters for retrieval
            as {key:value} mapping. Leave as an empty dict for no filtering.
        llm_backend (str, optional): LLM backend to use.
            Defaults to LLM_BACKEND_DEFAULT.
        llm_id (str, optional): LLM model ID to use.
            Defaults to LLM_MODEL_DEFAULT.
        embedding_model_id (str, optional): ID of the embedding model to use.
            Defaults to EMBEDDING_MODEL_DEFAULT.
        reranker_model_id (str | None, optional): Reranker model to use.
            Defaults to None.
        similarity_top_k (int, optional): Number of top results to retrieve.
            Defaults to SIMILARITY_TOP_K_DEFAULT.
        similarity_cutoff (float, optional): Similarity cutoff for retrieval.
            Defaults to SIMILARITY_CUTOFF_DEFAULT.
        vector_store_backend (str): Vector store backend to use.
            Defaults to settings.VECTOR_STORE_BACKEND.
        pubsub (bool, optional): Whether to use Pub/Sub for updates.
            Defaults to False.
    Returns:
        responses (list[QAResponse]): List of QAResponse objects containing the
        question, question type and answer for each question in the question library.
    """
    from flows.common.clients.llms import get_embedding_model, get_llm
    from flows.common.clients.vector_stores import get_vector_store
    from flows.shrag.playbook import build_question_library
    from flows.shrag.qa import QAgent

    def db_update_callback():
        """Closure to create a callback task that updates the MongoDB
        collection with the results of the QAgent run.
        This task will be called for each answer extracted by the QAgent.
        """
        results_query = {
            "meta_filters": meta_filters,
            "client_id": client_id,
            "collection": collection_name,
            "playbook_id": playbook.id,
            "playbook_version": playbook.version,
            "run_id": flow_run.id,
        }

        # The callback task defined in a closure so that it can access the db and query.
        @task(name="result_to_mongo")
        def _callback(update: dict[str, Any]):
            # Define a function to update the document in the MongoDB collection
            db.update_one(
                settings.MONGO_RESULTS_COLLECTION,
                filter=results_query,
                update=update,
                upsert=True,
            )
            attr = list(update.keys())[0].replace("answers.", "")
            pub(f"✅ Extracted '{attr}'")

        return _callback

    # Ensure meta_filters is a dict
    meta_filters: dict = meta_filters or {}

    # Update the metafilters to include:
    # The client_id, so that we only retrieve documents for the given client and
    # the LLM backend and embedding model so we ensure that the retrieval is
    # consistent with the LLM and embedding model used
    meta_filters.update(
        {
            "client_id": client_id,
            "llm_backend": llm_backend,
            "embedding_model": embedding_model_id,
        }
    )

    # Initialize the MongoDB client
    db = MongoDBClient()

    # Combine the logger and the publisher
    pub = pub_and_log(client_id, pubsub)

    # Get the LLM and embedding model
    llm = get_llm(llm_id=llm_id, llm_backend=llm_backend)
    embedding_model = get_embedding_model(
        llm_backend=llm_backend, embedding_model_id=embedding_model_id
    )

    # Get the ChromaDB index
    collection_name = get_default_vector_collection_name(
        vector_store_backend=vector_store_backend,
        client_id=client_id,
        llm_backend=llm_backend,
        embedding_model_id=embedding_model_id,
    )
    vec_store = get_vector_store(
        store_backend=vector_store_backend, embedding_model=embedding_model
    )
    index = vec_store.get_index(collection_name=collection_name)
    logger.info("🔍 Index loaded successfully!")

    # Init the QAgent
    pub("🤖 Initializing QAgent...")
    questioner = QAgent(
        index=index,
        llm=llm,
        reranker=reranker_model_id,
    )

    # Build the Question Library
    pub(f"📚 Building question library for playbook {playbook.name}")
    q_collection = build_question_library(playbook.definition)

    docs = vec_store.get_docs(
        collection_name=collection_name,
        filters={f"metadata.{k}": v for k, v in meta_filters.items()},
    )
    if not docs:
        logger.error(
            f"No documents found in collection '{collection_name}' "
            f"with filters: {meta_filters}"
        )
        raise RuntimeError("No documents found for the given filters. Aborting flow.")

    # Run the Q-collection and return the responses
    responses = questioner.run_q_collection(
        q_collection=q_collection,
        meta_filters=meta_filters,
        similarity_top_k=similarity_top_k,
        similarity_cutoff=similarity_cutoff,
        pbar=False,
        answer_callback_task=db_update_callback(),
    )

    # Invoke the callback to update the MongoDB with the timestamp of completion
    db_update_callback()(
        {
            "completed_at": dt.now().isoformat(),
        }
    )
    pub("🏁 QA Playbook run completed!")

    return {k: v.model_dump() for k, v in responses.items()}


PUBLIC_FLOWS: dict[str, Flow] = {
    run_qa_playbook.name: run_qa_playbook,
}
