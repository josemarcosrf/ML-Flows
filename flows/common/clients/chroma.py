from typing import Callable

import chromadb
from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.chroma import ChromaVectorStore
from loguru import logger
from tabulate import tabulate
from tqdm.rich import tqdm

from flows.common.clients.llms import LLMBackend
from flows.settings import settings


class ChromaClient:
    def __init__(self, host: str, port: int):
        self.db = chromadb.HttpClient(host, port)
        logger.info(f"🔌 Connected to ChromaDB at {host}:{port}")

    def create_collection(
        self,
        collection_name: str,
        embed_fn: Callable,
    ) -> chromadb.Collection:
        """Creates a new collection in the database

        Args:
            collection_name (str): Name of the collection to create
            embed_fn (Callable): Embedding function to use for the collection
        """
        # Check if the collection already exists
        if collection_name in self.db.list_collections():
            raise ValueError(f"💥 Collection {collection_name} already exists!")

        # Otherwise, create a new collection
        col = self.db.create_collection(collection_name, embedding_function=embed_fn)

        # Add metadata to the collection
        embed_model_name = embed_fn._model_name
        embedding_backend = embed_fn.__class__.__name__
        col_meta = col.metadata or {}
        if (
            "embedding_backend" in col_meta
            and col_meta["embedding_backend"] != embedding_backend
        ):
            raise ValueError(
                "⚠️ Collection marked as using a different embedding backend: "
                f"{col_meta['embedding_backend']}"
            )
        if (
            "embedding_model" in col_meta
            and col_meta["embedding_model"] != embed_model_name
        ):
            raise ValueError(
                "⚠️ Collection marked as using a different embedding model: "
                f"{col_meta['embedding_model']}"
            )

        col_meta["embedding_backend"] = embedding_backend
        col_meta["embedding_model"] = embed_model_name
        col.modify(metadata=col_meta)

        return col

    def get_collection(
        self,
        collection_name: str,
        create: bool = False,
        embed_fn: Callable | None = None,
    ):
        """Returns the collection from the database"""
        # Check if the collection exists
        if collection_name not in self.db.list_collections():
            if create:
                if embed_fn is None:
                    raise ValueError(
                        "💥 Please provide an embedding function to create the collection"
                    )

                # If it doesn't exist, create it
                logger.warning(f"🪣 Creating empty collection {collection_name}")
                chroma_collection = self.db.create_collection(collection_name)
            else:
                raise ValueError(
                    f"💥 Collection {collection_name} does not exist! Please create it first."
                )
        else:
            chroma_collection = self.db.get_collection(collection_name)
            if count := chroma_collection.count():
                logger.info(
                    f"🗳️ Collection {collection_name} exists! (Total vectors: {count})"
                )

        return chroma_collection

    def get_vector_store(self, embed_model, collection_name: str) -> ChromaVectorStore:
        """Returns the vector store from the database"""
        logger.debug(f"🔍 Getting vector store for collection {collection_name}")
        col = self.get_collection(collection_name)
        return ChromaVectorStore(chroma_collection=col, embed_model=embed_model)

    def get_index(self, embed_model, collection_name: str) -> VectorStoreIndex:
        """Returns the index from the database"""
        logger.debug(f"🔍 Getting index for collection {collection_name}")
        vector_store = self.get_vector_store(embed_model, collection_name)
        return VectorStoreIndex.from_vector_store(vector_store, embed_model)

    def get_embedding_function(
        self, backend: str | LLMBackend, embedding_model: str, **kwargs
    ):
        """Returns the embedding function for the database

        Args:
            backend (str | LLMBackend): LLM backend to use. One of openai, ollama
            embedding_model (str): Embedding model to use. E.g.: text-embedding-3-small, nomic-embed-text, ...
            **kwargs: Additional keyword arguments to pass to the embedding function
                ollama_base_url (str): Host of the Ollama server. Defaults to localhost:11434
                openai_api_key (str): API key for the OpenAI API. Defaults to None
                    (uses the OPENAI_API_KEY environment variable)
        Raises:
            ValueError: If the LLM backend is not one of openai, ollama
            ValueError: If the extra keyword arguments are not valid for the embedding function
        Returns:
            _type_: _description_
        """
        if backend == LLMBackend.OLLAMA:
            from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

            if ollama_base_url := (
                kwargs.get("ollama_base_url") or settings.OLLAMA_BASE_URL
            ):
                return OllamaEmbeddingFunction(
                    url=f"{ollama_base_url}/api/embeddings",
                    model_name=embedding_model,
                )
            else:
                raise ValueError(
                    "❌ Missing Ollama host. Please provide it as a keyword argument "
                    "or set the OLLAMA_BASE_URL environment variable."
                    "E.g.: OLLAMA_BASE_URL=http://localhost:11434"
                )

        elif backend == LLMBackend.OPENAI:
            from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

            return OpenAIEmbeddingFunction(
                api_key=kwargs.get("openai_api_key") or settings.OPENAI_API_KEY,
                model_name=embedding_model,
            )

        else:
            raise ValueError(
                f"❌ Unknown LLM backend: {backend}. Please use one of {LLMBackend.__members__}"
            )

    def print_collection_contents(
        self, collection_name: str, metadata_fields: list[str], batch_size: int = 256
    ):
        """Fetches all Chroma collection items' in batches to avoid memory issues and
        prints the contents in table format. Rows are sorted by the first metadata field.
        Args:
            collection_name (str): Name of the collection to print
            metadata_fields (list[str]): List of metadata fields to print
            batch_size (int, optional): Number of items to fetch per batch. Defaults to 256.
                Note: This is a trade-off between memory usage and performance.
                A smaller batch size will use less memory but will be slower.
                A larger batch size will be faster but will use more memory.
                The default value of 256 is a good balance between memory usage and performance.
        """

        def get_cols(meta):
            return tuple(meta.get(field) for field in metadata_fields)

        def get_batch_metas(batch_size, offset):
            return col.get(include=["metadatas"], limit=batch_size, offset=offset)[
                "metadatas"
            ]

        col = self.db.get_collection(collection_name)  # type: ignore[union-attr]

        if total_count := col.count():
            print(f"Total items in collection '{collection_name}': {total_count} ")
            sources = []
            for offset in tqdm(range(0, total_count, batch_size), desc="Scanning..."):
                if metas := get_batch_metas(batch_size, offset):
                    sources.extend(
                        [get_cols(m) for m in metas if None not in [get_cols(m)]]
                    )

            docs = sorted(set(sources), key=lambda x: x[0])  # type: ignore
            print(
                tabulate(
                    docs,
                    headers=[m.upper() for m in metadata_fields],
                    tablefmt="fancy_grid",
                )
            )
        else:
            print("👀 No documents found!")
