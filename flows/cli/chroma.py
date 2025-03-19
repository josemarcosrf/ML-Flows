import click

from flows.settings import settings


@click.group("chroma")
@click.option("--host", default=settings.CHROMA_HOST)
@click.option("--port", default=settings.CHROMA_PORT)
def chroma_cli(host, port):
    """ChromaDB CLI"""
    from flows.common.clients.chroma import ChromaClient

    print(f"🔌 Connecting to chroma at: {host}:{port}")
    global client
    client = ChromaClient(host, port)


@chroma_cli.command("ls")
def list_collections():
    """List all collections in the ChromaDB"""
    print("================ Collections ================")
    for collection in client.db.list_collections():
        print(f"- {collection}")

    print("✨ Done!")


@chroma_cli.command("lsd")
@click.argument("collection_name")
@click.option("-m", "--metadata-fields", default=["name", "doc_id"], multiple=True)
def list_collection_documents(
    collection_name: str,
    metadata_fields: list[str],
):
    """List a ChromaDB's collection contents"""
    print(f"================ Collection {collection_name} ================")
    client.print_collection_documents(
        collection_name=collection_name, metadata_fields=metadata_fields
    )
    print("✨ Done!")


client = None
