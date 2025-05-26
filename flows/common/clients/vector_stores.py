from enum import Enum
from typing import Any

from llama_index.core import VectorStoreIndex
from loguru import logger
from tabulate import tabulate
from tqdm.rich import tqdm

from flows.common.clients.embeddings import get_embedding_function
from flows.common.clients.llms import embedding_model_info
from flows.settings import settings


class VectorStoreBackend(str, Enum):
    MONGO = "mongo"
    CHROMA = "chroma"


class VectorStore:
    def get_doc(
        self, doc_id: str, collection_name: str = "...", **kwargs
    ) -> list | None:
        raise NotImplementedError

    def get_vector_store(self, collection_name: str = "...", **kwargs):
        raise NotImplementedError

    def get_index(self, collection_name: str = "...", **kwargs):
        raise NotImplementedError

    def create_index(self, collection_name: str = "...", **kwargs):
        raise NotImplementedError

    def print_collection_documents(
        self,
        collection_name: str = "...",
        metadata_fields: list[str] = ["name", "subdir"],
        **kwargs,
    ):
        raise NotImplementedError


class MongoVectorStore(VectorStore):
    def __init__(
        self,
        embed_model,
        uri: str = settings.MONGO_URI,
        db_name: str = settings.MONGO_DB,
    ):
        from llama_index.vector_stores.mongodb import MongoDBAtlasVectorSearch
        from pymongo import MongoClient

        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        logger.info(f"🔌 Connected to MongoDB at {uri} | DB: {db_name}")
        self.embed_model = embed_model
        self._MongoDBAtlasVectorSearch = MongoDBAtlasVectorSearch

    def _create_collection(self, collection_name: str) -> Any:
        """
        Create a new collection in the MongoDB database.
        Args:
            collection_name (str): The name of the collection to create.
        Returns:
            Collection: The created collection.
        """
        logger.info(f"🪣 Creating collection '{collection_name}'")
        return self.db.create_collection(collection_name)

    def _get_collection(self, collection_name: str) -> Any:
        """
        Get the collection from the MongoDB database.
        Args:
            collection_name (str): The name of the collection to get.
        Returns:
            Collection: The collection object.
        """
        logger.debug(f"🔍 Getting collection '{collection_name}'")
        if collection_name not in self.db.list_collection_names():
            raise ValueError(f"💥 Collection '{collection_name}' does not exist! ")

        logger.info(f"🗳️ Collection '{collection_name}' exists!")

        return self.db[collection_name]

    def _get_vector_store(self, collection_name: str, vector_index_name: str):
        """
        Get the vector store for the specified collection.
        Args:
            collection_name (str): The name of the collection to get the vector store for.
            **kwargs: Additional keyword arguments, such as vector_index_name.
        Returns:
            MongoDBAtlasVectorSearch: The vector store for the specified collection.
        """
        logger.debug(f"🔍 Getting vector store for collection {collection_name}")
        return self._MongoDBAtlasVectorSearch(
            self.client,
            db_name=self.db.name,
            collection_name=collection_name,
            vector_index_name=vector_index_name,
        )

    def _index_exists(self, collection_name, index_name: str) -> bool:
        indexes = self._get_collection(collection_name).list_search_indexes()
        for index in indexes:
            if index.get("name") == index_name:
                return True
        return False

    def _create_index(
        self,
        collection_name: str,
        vector_index_name: str,
        index_filters: list[str] = ["name", "subdir"],
    ) -> VectorStoreIndex:
        """Create a vector index for the specified collection.
        This method checks if the index already exists, and if not, creates it
        with the specified embedding model and similarity function.
        If the index already exists, it logs a warning and does not create a new one.

        Args:
            collection_name (str): The name of the collection to create the index for.
            **kwargs: Additional keyword arguments, such as vector_index_name and index_filters.
        Raises:
            ValueError: If the index already exists.
        Returns:
            _type_: _description_
        """

        vec_dimensions, similarity = embedding_model_info(self.embed_model)
        store = self.get_vector_store(
            collection_name=collection_name, vector_index_name=vector_index_name
        )
        if not self._index_exists(store.collection, vector_index_name):
            logger.info(f"🪣 Creating index '{vector_index_name}'")
            store.create_vector_search_index(
                dimensions=vec_dimensions,
                path="embedding",
                similarity=similarity,
                filters=index_filters,
            )
            logger.info("✅ Index created successfully.")
        else:
            logger.warning(f"Index '{vector_index_name}' already exists")

        return VectorStoreIndex.from_vector_store(store, embed_model=self.embed_model)

    def get_index(self, collection_name: str, create: bool = False, **kwargs):
        vector_index_name = kwargs.get(
            "vector_index_name", settings.MONGO_VECTOR_INDEX_NAME
        )
        logger.debug(f"🔍 Getting index for collection {collection_name}")
        store = self._get_vector_store(
            collection_name=collection_name, vector_index_name=vector_index_name
        )
        if not self._index_exists(store.collection, vector_index_name):
            logger.warning("💥 Non existing / Empty Index!")
            if create:
                logger.info(
                    f"💥 Collection '{collection_name}' does not exist! "
                    "Creating a new collection and index."
                )
                self._create_collection(collection_name=collection_name)
                return self._create_index(
                    collection_name=collection_name, vector_index_name=vector_index_name
                )
            else:
                raise ValueError(
                    f"❌ Vector index '{vector_index_name}' does not exist "
                    f"in collection '{collection_name}'. "
                    "Please ensure the index is created and populated with data."
                )
        index = VectorStoreIndex.from_vector_store(store, embed_model=self.embed_model)
        logger.info("✅ Index loaded successfully.")
        return index

    def get_doc(
        self,
        doc_id: str,
        collection_name: str,
    ) -> list[dict] | None:
        """
        Get a document by its ID from the specified collection.
        Args:
            collection_name (str): The name of the collection to get the document from.
            doc_id (str): The ID of the document to retrieve.
        Returns:
            dict: The document with the specified ID, or None if not found.
        """
        col = self._get_collection(collection_name)
        return list(col.find({"metadata.doc_id": doc_id}))

    def print_collection(
        self,
        collection_name: str,
        metadata_fields: list[str] = ["doc_id", "subdir", "name"],
        **kwargs,
    ):
        col = self._get_collection(collection_name)

        def get_cols(doc):
            meta = doc.get("metadata", {})
            return tuple(meta.get(k, "n/d") for k in metadata_fields)

        items = list(col.find())
        if total_count := len(items):
            print(f"Total items in collection '{col.name}': {total_count} ")
            docs = {get_cols(item) for item in items}
            print(
                tabulate(
                    docs,
                    headers=[m.upper() for m in metadata_fields],
                    tablefmt="fancy_grid",
                )
            )
        else:
            print("👀 No documents found!")


class ChromaVectorStore(VectorStore):
    def __init__(
        self,
        embed_model,
        host: str = settings.CHROMA_HOST,
        port: int = settings.CHROMA_PORT,
    ):
        import chromadb
        from llama_index.vector_stores.chroma import ChromaVectorStore as CVS

        self.embed_model = embed_model
        self.db = chromadb.HttpClient(host, port)
        logger.info(f"🔌 Connected to ChromaDB at {host}:{port}")
        self._CVS = CVS

    def _create_collection(
        self,
        collection_name: str,
        **kwargs: Any,
    ):
        """Creates a new collection in the database

        Args:
            collection_name (str): Name of the collection to create
            embed_fn (Callable): Embedding function to use for the collection
        """
        # Check if the collection already exists
        if collection_name in self.db.list_collections():
            raise ValueError(f"💥 Collection {collection_name} already exists!")

        # Get the embedding function based on the embed model
        embed_model_name = self.embed_model.model_name
        embed_fn = get_embedding_function(
            embed_model_name,
            kwargs.get("llm_backend", settings.LLM_BACKEND),
        )

        embedding_backend = embed_fn.__class__.__name__

        # Otherwise, create a new collection
        col = self.db.create_collection(collection_name, embedding_function=embed_fn)

        # Add metadata to the collection
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

    def _get_collection(
        self,
        collection_name: str,
    ):
        """Returns the collection from the database"""
        # Check if the collection exists
        chroma_collection = self.db.get_collection(collection_name)
        if count := chroma_collection.count():
            logger.info(
                f"🗳️ Collection {collection_name} exists! (Total vectors: {count})"
            )

        return chroma_collection

    def _get_vector_store(self, collection_name: str, **kwargs: Any):
        logger.debug(f"🔍 Getting vector store for collection {collection_name}")
        col = self.db.get_collection(collection_name)
        return self._CVS(chroma_collection=col, embed_model=self.embed_model)

    def _index_exists(self, collection_name: str, **kwargs) -> bool:
        """
        Check if the index exists (i.e.: if the collection exists).
        Args:
            collection_name (str): The name of the collection to check.
        Returns:
            bool: True if the index exists, False otherwise.
        """
        col = self.db.get_collection(collection_name)
        return col.count() > 0

    def _create_index(self, collection_name: str, **kwargs) -> VectorStoreIndex:
        """
        Create a vector index for the specified collection.
        This method checks if the index already exists, and if not, creates it
        with the specified embedding model and similarity function.
        If the index already exists, it logs a warning and does not create a new one.

        Args:
            collection_name (str): The name of the collection to create the index for.
            **kwargs: Additional keyword arguments, such as vector_index_name and index_filters.
        Raises:
            ValueError: If the index already exists.
        Returns:
            VectorStoreIndex: The created vector store index.
        """
        store = self._get_vector_store(collection_name=collection_name)
        if not self._index_exists(collection_name):
            logger.info(f"🪣 Creating index for collection {collection_name}")
            return store.create_collection()
        else:
            logger.warning(f"Index for collection {collection_name} already exists")
            return self.get_index(collection_name)

    def get_index(self, collection_name: str, create: bool = False, **kwargs):
        logger.debug(f"🔍 Getting index for collection {collection_name}")

        if not self._index_exists(collection_name):
            if create:
                logger.info(
                    f"💥 Collection {collection_name} does not exist! "
                    "Creating a new collection."
                )
                self._create_collection(collection_name=collection_name)
            else:
                raise ValueError(
                    f"❌ Vector index for collection '{collection_name}' does not exist. "
                    "Please ensure the index is created and populated with data."
                )

        vector_store = self.get_vector_store(collection_name)
        return VectorStoreIndex.from_vector_store(
            vector_store, embed_model=self.embed_model
        )

    def get_doc(
        self,
        doc_id: str,
        collection_name: str,
        **kwargs: Any,
    ) -> list | None:
        """
        Get a document by its ID from the specified collection.
        Args:
            collection_name (str): The name of the collection to get the document from.
            doc_id (str): The ID of the document to retrieve.
        Returns:
            dict: The document with the specified ID, or None if not found.
        """
        col = self.db.get_collection(collection_name)
        include = kwargs.get("include", ["metadatas"])
        return col.get(ids=[doc_id], include=include).get("metadatas")

    def _get_collection_documents(
        self,
        collection_name: str,
        metadata_fields: list[str] = ["name", "subdir"],
        batch_size: int = 256,
    ) -> list[dict]:
        def get_cols(meta):
            return tuple(meta.get(field) for field in metadata_fields)

        def get_batch_metas(batch_size, offset):
            # chromadb expects include to be a string, not a list
            return col.get(include=["metadatas"], limit=batch_size, offset=offset)[
                "metadatas"
            ]

        col = self.db.get_collection(collection_name)
        sources = []
        total_count = col.count()
        if total_count:
            for offset in tqdm(range(0, total_count, batch_size), desc="Scanning..."):
                metas = get_batch_metas(batch_size, offset)
                if metas:
                    sources.extend(
                        [get_cols(m) for m in metas if None not in [get_cols(m)]]
                    )
        docs = sorted(set(sources), key=lambda x: x[0]) if sources else []
        return docs

    def print_collection(
        self,
        collection_name: str,
        metadata_fields: list[str] = ["name", "subdir"],
        batch_size: int = 256,
        **kwargs,
    ):
        docs = self._get_collection_documents(
            collection_name, metadata_fields, batch_size=batch_size
        )
        if docs:
            print(f"Total items in collection '{collection_name}': {len(docs)} ")
            print(
                tabulate(
                    docs,
                    headers=[m.upper() for m in metadata_fields],
                    tablefmt="fancy_grid",
                )
            )
        else:
            print("👀 No documents found!")


def get_vector_store(store_backend: str, embed_model, **kwargs) -> VectorStore:
    if store_backend.lower() == VectorStoreBackend.MONGO:
        return MongoVectorStore(embed_model, **kwargs)
    elif store_backend.lower() == VectorStoreBackend.CHROMA:
        return ChromaVectorStore(embed_model, **kwargs)
    else:
        raise ValueError(f"Unknown vector store backend: {store_backend}")
