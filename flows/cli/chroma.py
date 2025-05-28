import click

from flows.settings import settings


@click.group("chroma")
@click.option("--host", default=settings.CHROMA_HOST)
@click.option("--port", default=settings.CHROMA_PORT)
@click.pass_context
def chroma_cli(ctx, host, port):
    """ChromaDB CLI"""
    from flows.common.clients.vector_stores import ChromaVectorStore

    print(f"🔌 Connecting to chroma at: {host}:{port}")
    ctx.ensure_object(dict)
    ctx.obj["client"] = ChromaVectorStore(None, host, port)


@chroma_cli.command("ls")
@click.pass_context
def list_collections(ctx):
    """List all collections in the ChromaDB"""
    client = ctx.obj["client"]
    print("================ Collections ================")
    for collection in client.db.list_collections():
        print(f"- {collection}")

    print("✨ Done!")


@chroma_cli.command("lsd")
@click.argument("collection_name")
@click.option("-m", "--metadata-fields", default=["name", "doc_id"], multiple=True)
@click.pass_context
def list_collection_documents(ctx, collection_name: str, metadata_fields: list[str]):
    """List a ChromaDB's collection contents"""
    client = ctx.obj["client"]
    print(f"================ Collection {collection_name} ================")
    client.print_collection(
        collection_name=collection_name, metadata_fields=metadata_fields
    )
    print("✨ Done!")


@chroma_cli.command("rm")
@click.argument("collection_name")
@click.pass_context
def remove_collection(ctx, collection_name: str):
    """Remove a collection from the ChromaDB"""
    client = ctx.obj["client"]
    client.db.delete_collection(collection_name)
    print(f"🗑️ Collection {collection_name} removed!")


@chroma_cli.command("rmd")
@click.argument("collection_name")
@click.argument("doc_id")
@click.pass_context
def remove_document(ctx, collection_name: str, doc_id: str):
    """Remove a document from the ChromaDB"""
    client = ctx.obj["client"]
    collection = client.db.get_collection(collection_name)
    collection.delete(where={"doc_id": doc_id})
    print(f"🗑️ Document {doc_id} removed from collection {collection_name}!")
