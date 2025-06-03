import os

import click
from dotenv import load_dotenv
from llama_index.core.vector_stores import MetadataFilters
from tabulate import tabulate

from flows.common.clients.llms import get_embedding_model
from flows.common.clients.vector_stores import (
    get_default_vector_collection_name,
    get_vector_store,
)
from flows.shrag.qa import build_filter

load_dotenv()


def parse_filters(filters: list[str]) -> dict[str, list[str]]:
    filter_dict = {}
    for f in filters:
        if ":" not in f:
            raise click.ClickException(f"Invalid filter format: {f}. Use key:value.")
        k, v = f.split(":", 1)
        if k in filter_dict:
            if isinstance(filter_dict[k], list):
                filter_dict[k].append(v)
            else:
                filter_dict[k] = [filter_dict[k], v]
        else:
            filter_dict[k] = v

    # Convert single values to list if key appears multiple times
    for k, v in filter_dict.items():
        if isinstance(v, list):
            filter_dict[k] = v

    print("🔍 Using filters:", filter_dict)
    return filter_dict


@click.command()
@click.argument(
    "store-backend", type=click.Choice(["mongo", "chroma"], case_sensitive=False)
)
@click.argument("query", type=str)
@click.option(
    "--llm-backend",
    default=os.environ.get("LLM_BACKEND", "default-llm-backend"),
    help="LLM backend to use (default: from environment variable).",
)
@click.option(
    "-e",
    "--embedding-model",
    default=os.environ.get("EMBEDDING_MODEL", "default-embedding-model"),
    help="Embedding model to use (default: from environment variable).",
)
@click.option(
    "-c",
    "--collection-name",
    default=None,
    help="Name of the vector store collection (default: auto-generated).",
)
@click.option(
    "-f",
    "--filter",
    "filters",
    multiple=True,
    help="Metadata filter in key:value format. Can be repeated.",
)
@click.option(
    "-k",
    "--top-k",
    "top_k",
    default=5,
    type=int,
    help="Number of top results to retrieve (default: 5).",
)
def main(
    store_backend, query, filters, top_k, llm_backend, embedding_model, collection_name
):
    """
    CLI to test the retriever with MongoDB backend and flexible metadata filters.
    """
    # Parse filters into a dict, supporting multiple values per key
    filter_dict = parse_filters(filters)

    # If no collection name is provided, use the default based on the backend and model
    collection_name = collection_name or get_default_vector_collection_name(
        vector_store_backend=store_backend,
        llm_backend=llm_backend,
        embedding_model=embedding_model,
    )

    # Get the embedding model and vector store based on the provided backends
    embedding_model = get_embedding_model(
        llm_backend=llm_backend,
        embedding_model=embedding_model,
    )
    vector_store = get_vector_store(
        store_backend=store_backend, embed_model=embedding_model
    )

    # Compose metadata filters if any filters are provided
    meta_filters = (
        MetadataFilters(filters=[build_filter(k, v) for k, v in filter_dict.items()])
        if filter_dict
        else None
    )

    # Build the retriever with the specified collection name and filters
    index = vector_store.get_index(collection_name=collection_name)
    retriever = index.as_retriever(filters=meta_filters, similarity_top_k=top_k)

    # Perform the retrieval & display results
    results = retriever.retrieve(query)
    print("\n🗂️ Retrieved document nodes:\n")
    if results:
        headers = results[0].metadata.keys()
        rows = [doc.metadata.values() for doc in results]
        print(tabulate(rows, headers=headers, tablefmt="grid"))
    else:
        print("👀 No documents nodes found.")


if __name__ == "__main__":
    main()
