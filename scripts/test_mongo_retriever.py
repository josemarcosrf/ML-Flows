import os

import click
from dotenv import load_dotenv
from llama_index.core.vector_stores import MetadataFilters
from tabulate import tabulate

from flows.common.clients.llms import get_embedding_model
from flows.common.clients.vector_stores import get_vector_store
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

    for k, v in filter_dict.items():
        if not k.startswith("metadata."):
            filter_dict[f"metadata.{k}"] = filter_dict.pop(k)

    print("🔍 Using filters:", filter_dict)
    return filter_dict


@click.command()
@click.argument("query", type=str)
@click.option(
    "-f",
    "--filter",
    "filters",
    multiple=True,
    help="Metadata filter in key:value format. Can be repeated.",
)
def main(query, filters):
    """
    CLI to test the retriever with MongoDB backend and flexible metadata filters.
    """
    # Parse filters into a dict, supporting multiple values per key
    filter_dict = parse_filters(filters)

    embedding_model = get_embedding_model(
        llm_backend=os.environ["LLM_BACKEND"],
        embedding_model=os.environ["EMBEDDING_MODEL"],
    )
    vector_store = get_vector_store(store_backend="mongo", embed_model=embedding_model)
    index = vector_store.get_index(collection_name="embeddings")
    meta_filters = MetadataFilters(
        filters=[build_filter(k, v) for k, v in filter_dict.items()]
    )
    retriever = index.as_retriever(filters=meta_filters, similarity_top_k=5)
    results = retriever.retrieve(query)
    print("🗂️ Retrieved documents:")
    if results:
        headers = results[0].metadata.keys()
        rows = [doc.metadata.values() for doc in results]
        print(tabulate(rows, headers=headers, tablefmt="grid"))
    else:
        print("👀 No documents found.")


if __name__ == "__main__":
    main()
