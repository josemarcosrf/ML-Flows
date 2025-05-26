import json
from functools import wraps
from pathlib import Path

import click

from flows.common.clients.llms import LLMBackend
from flows.common.clients.vector_stores import VectorStoreBackend
from flows.common.types import Playbook
from flows.settings import settings
from flows.shrag import playbook_qa
from flows.shrag.playbook import build_question_library, read_playbook_json


def common_rag_options(func):
    @click.argument("client_id")
    @click.argument("collection")
    @click.argument("playbook_json")
    @click.option(
        "--vector-store-backend",
        default=settings.VECTOR_STORE_BACKEND,
        type=click.Choice([e.value for e in VectorStoreBackend]),
    )
    @click.option(
        "--llm-backend",
        default=settings.LLM_BACKEND,
        type=click.Choice([e.value for e in LLMBackend]),
    )
    @click.option("--llm-model", default=settings.LLM_MODEL)
    @click.option("--embedding-model", default=settings.EMBEDDING_MODEL)
    @click.option("--reranker-model", default=None)
    @click.option("--similarity-top-k", type=int, default=settings.SIMILARITY_TOP_K)
    @click.option("--similarity-cutoff", type=float, default=settings.SIMILARITY_CUTOFF)
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


@click.group("rag")
def shrag_cli():
    """Structured RAG CLI"""


@shrag_cli.command()
@click.argument("input-directory")
@click.argument("output-directory")
@common_rag_options
@click.option("-fg", "--file-glob", default="*.pdf", help="File glob pattern")
def run_playbook_qa_from_directory(
    client_id: str,
    collection: str,
    input_directory: str,
    output_directory: str,
    playbook_json: str,
    vector_store_backend: str,
    llm_backend: str,
    llm_model: str,
    embedding_model: str,
    reranker_model: str | None,
    similarity_top_k: int,
    similarity_cutoff: float,
    file_glob: str,
):
    """Runs the RAG dataflow on all document files in the specified directory
    using the document names as metafilters.

    Args:
        directory (str): Path to the directory containing playbook JSON files.
        collection (str): Name of the embedding collection to use.
        llm_backend (str, optional): LLM backend to use. Defaults to "openai".
        llm_model (str, optional): LLM model to use. Defaults to "gpt-4o".
        embedding_model (str, optional): Embedding model to use. Defaults to "text-embedding-3-small".
        reranker_model (str | None, optional): Reranker model to use. Defaults to None.
        similarity_top_k (int, optional): Number of top results to retrieve. Defaults to 5.
        similarity_cutoff (float, optional): Similarity cutoff for retrieval. Defaults to 0.3.
        file_glob (str, optional): File glob pattern. Defaults to "*.canonical.pdf".
    """

    # Iterate over all Document files in the directory
    for filename in Path(input_directory).rglob(file_glob):
        if filename.is_file():
            ext = file_glob.replace("*", "")
            fname = filename.name.replace(ext, "")
            print(f"⚙️ Processing {fname}")

            # Read the playbook JSON file
            playbook = Playbook(
                id=Path(playbook_json).stem,
                name=Path(playbook_json).stem,
                definition=build_question_library(read_playbook_json(playbook_json)),
            )

            # Run the RAG dataflow
            meta_filters = {"name": fname}
            res = playbook_qa(
                client_id=client_id,
                collection=collection,
                playbook=playbook,
                meta_filters=meta_filters,
                llm_backend=llm_backend,
                llm_model=llm_model,
                embedding_model=embedding_model,
                reranker_model=reranker_model,
                similarity_top_k=similarity_top_k,
                similarity_cutoff=similarity_cutoff,
                vector_store_backend=vector_store_backend,
            )
            # Write the results to a file; concatenate the filters to the file name
            filters = "_".join(f"{k}={v}" for k, v in meta_filters.items())
            result_filename = f"{filters}_qa_results.json"

            out_dir = Path(output_directory)
            if not out_dir.exists():
                out_dir.mkdir(parents=True)

            with (out_dir / result_filename).open("w") as f:
                f.write(json.dumps(res, indent=2))


@shrag_cli.command()
@common_rag_options
@click.option(
    "-m",
    "--meta_filters",
    multiple=True,
    type=str,
    help="Additional key:value pairs to be parsed as metadata filters",
)
def run_playbook_qa(
    client_id: str,
    playbook_json: str,
    meta_filters: str,
    collection: str,
    vector_store_backend: str,
    llm_backend: str,
    llm_model: str,
    embedding_model: str,
    reranker_model: str | None,
    similarity_top_k: int,
    similarity_cutoff: float,
):
    """Runs the RAG dataflow on the specified question library and documents as
    returned by the metadata filters and writes the results to a JSON file.

    Args:
        client_id (str): Client ID for the Pub/Sub updates.
        playbook_json (str): Path to the playbook JSON file.
        collection (str): Name of the embedding collection to use.
        vector_store_backend (str): Vector store backend to use.
        llm_backend (str, optional): LLM backend to use. Defaults to "openai".
        llm_model (str, optional): LLM model to use. Defaults to "gpt-4o".
        embedding_model (str, optional): Embedding model to use. Defaults to "text-embedding-3-small".
        reranker_model (str | None, optional): Reranker model to use. Defaults to None.
        similarity_top_k (int, optional): Number of top results to retrieve. Defaults to 5.
        similarity_cutoff (float, optional): Similarity cutoff for retrieval. Defaults to 0.3.
        meta_filters (str): Metadata filters to apply to the questions.
    """
    # Parse additional_params into a dictionary
    filters = dict(param.split(":") for param in meta_filters) if meta_filters else {}

    # Read the playbook JSON file
    playbook = Playbook(
        id=Path(playbook_json).stem,
        name=Path(playbook_json).stem,
        definition=build_question_library(read_playbook_json(playbook_json)),
    )

    # Run the RAG dataflow
    res = playbook_qa(
        client_id=client_id,
        collection=collection,
        playbook=playbook,
        meta_filters=filters,
        llm_backend=llm_backend,
        llm_model=llm_model,
        embedding_model=embedding_model,
        reranker_model=reranker_model,
        similarity_top_k=similarity_top_k,
        similarity_cutoff=similarity_cutoff,
        vector_store_backend=vector_store_backend,
    )
    # Write the results to a file; concatenate the filters to the file name
    filters = "_".join(f"{k}={v}" for k, v in meta_filters.items())
    with open(f"{filters}_qa_results.json", "w") as f:
        f.write(json.dumps(res, indent=2))
