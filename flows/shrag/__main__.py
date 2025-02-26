import os

import click

from flows.shrag import playbook_qa
from flows.shrag.constants import (
    CHROMA_HOST_DEFAULT,
    CHROMA_PORT_DEFAULT,
    EMBEDDING_MODEL_DEFAULT,
    EMBEDDING_MODEL_ENV_VAR,
    LLM_BACKEND_DEFAULT,
    LLM_BACKEND_ENV_VAR,
    LLM_MODEL_DEFAULT,
    LLM_MODEL_ENV_VAR,
    SIMILARITY_CUTOFF_DEFAULT,
    SIMILARITY_TOP_K_DEFAULT,
)


@click.group()
def cli():
    """Welcome to the SHRAG's Command Line Interface"""


@cli.command()
@click.argument("question_library_csv")
@click.argument("proto_questions_json")
@click.argument("collection_name")
@click.option(
    "-m",
    "--meta_filters",
    multiple=True,
    type=str,
    help="Additional key:value pairs to be parsed as metadata filters",
)
@click.option(
    "--llm-backend", default=os.getenv(LLM_BACKEND_ENV_VAR, LLM_BACKEND_DEFAULT)
)
@click.option("--llm-model", default=os.getenv(LLM_MODEL_ENV_VAR, LLM_MODEL_DEFAULT))
@click.option(
    "--embedding-model",
    default=os.getenv(EMBEDDING_MODEL_ENV_VAR, EMBEDDING_MODEL_DEFAULT),
)
@click.option("--chroma-host", default=CHROMA_HOST_DEFAULT)
@click.option("--chroma-port", type=int, default=CHROMA_PORT_DEFAULT)
@click.option("--reranker-model", default=None)
@click.option("--similarity-top-k", type=int, default=SIMILARITY_TOP_K_DEFAULT)
@click.option("--similarity-cutoff", type=float, default=SIMILARITY_CUTOFF_DEFAULT)
def run_playbook_qa(
    question_library_csv: str,
    proto_questions_json: str,
    collection_name: str,
    meta_filters: str,
    llm_backend: str,
    llm_model: str,
    embedding_model: str,
    chroma_host: str,
    chroma_port: int,
    reranker_model: str | None,
    similarity_top_k: int,
    similarity_cutoff: float,
):
    """Runs the RAG dataflow on the specified question library and proto questions.
    Args:
        question_library_csv (str): Path to the question library CSV file.
        proto_questions_json (str): Path to the proto questions JSON file.
        collection_name (str): Name of the collection to use.
        meta_filters (str): Metadata filters to apply to the questions.
        llm_backend (str, optional): LLM backend to use. Defaults to "openai".
        llm_model (str, optional): LLM model to use. Defaults to "gpt-4o".
        embedding_model (str, optional): Embedding model to use. Defaults to "text-embedding-3-small".
        reranker_model (str | None, optional): Reranker model to use. Defaults to None.
        similarity_top_k (int, optional): Number of top results to retrieve. Defaults to 5.
        similarity_cutoff (float, optional): Similarity cutoff for retrieval. Defaults to 0.3.
        chroma_host (str, optional): ChromaDB host. Defaults to "localhost".
        chroma_port (int, optional): ChromaDB port. Defaults to 8000.
    """
    # Parse additional_params into a dictionary
    meta_filters = (
        dict(param.split(":") for param in meta_filters) if meta_filters else {}
    )

    # Run the RAG dataflow
    playbook_qa(
        question_library_csv=question_library_csv,
        proto_questions_json=proto_questions_json,
        collection_name=collection_name,
        meta_filters=meta_filters,
        llm_backend=llm_backend,
        llm_model=llm_model,
        embedding_model=embedding_model,
        reranker_model=reranker_model,
        similarity_top_k=similarity_top_k,
        similarity_cutoff=similarity_cutoff,
        chroma_host=chroma_host,
        chroma_port=chroma_port,
    )


if __name__ == "__main__":
    cli()
