from enum import Enum
from typing import Any

from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.embeddings import BaseEmbedding
from loguru import logger
from tabulate import tabulate
from tqdm.rich import tqdm

from flows.common.clients.embeddings import get_embedding_function
from flows.common.clients.llms import embedding_model_info
from flows.common.helpers import sanitize_uri
from flows.settings import settings


class CollectionNotFoundError(Exception):
    """Exception raised when a collection is not found in the vector store."""

    def __init__(self, collection_name: str):
        super().__init__(f"💥 Collection '{collection_name}' not found in the DB.")
        self.collection_name = collection_name


class VectorStoreIndexNotFoundError(Exception):
    """Exception raised when a vector store index is not found."""

    def __init__(self, collection_name: str, index_name: str):
        super().__init__(
            f"💥 Vector store index '{index_name}' not found in "
            f"collection '{collection_name}'"
        )
        self.collection_name = collection_name
        self.index_name = index_name


class VectorStoreBackend(str, Enum):
    MONGO = "mongo"
    CHROMA = "chroma"


class VectorStore:
    def get_docs(
        self, collection_name: str, filters: dict[str, Any], **kwargs
    ) -> list | None:
        raise NotImplementedError

    def delete_docs(
        self, collection_name: str, filters: dict[str, Any], **kwargs
    ) -> None:
        """Delete a document by its ID from the specified collection."""
        raise NotImplementedError

    def get_index(
        self, collection_name: str, create_if_not_exists: bool = False, **kwargs
    ):
        raise NotImplementedError

    def print_collection(
        self,
        collection_name: str,
        metadata_fields: list[str] = ["name", "subdir"],
        **kwargs,
    ):
        raise NotImplementedError


class MongoVectorStore(VectorStore):
    DEFAULT_INDEX_FIELDS = [
        "metadata.name",
        "metadata.subdir",
        "metadata.doc_id",
        "metadata.client_id",
        "metadata.project_id",
        "metadata.supabase_id",
        "metadata.llm_backend",
        "metadata.embedding_model",
        "metadata.vector_store_backend",
    ]

    def __init__(
        self,
        embedding_model: BaseEmbedding,
        uri: str = settings.MONGO_URI,
        db_name: str = settings.MONGO_DB,
    ):
        """Initialize the MongoDB vector store client.

        Args:
            embedding_model (BaseEmbedding): The embedding model instance to use for vectorization.
            uri (str, optional): Mongo connection URI with user and password if required.
                Defaults to settings.MONGO_URI.
            db_name (str, optional): Name of the Database where to store documents.
                Defaults to settings.MONGO_DB.
        """
        from llama_index.vector_stores.mongodb import MongoDBAtlasVectorSearch
        from pymongo import MongoClient

        self.client = MongoClient(uri)
        self.db = self.client[db_name]

        logger.info(f"🔌 Connected to MongoDB at {sanitize_uri(uri)} | DB: {db_name}")
        self.embedding_model = embedding_model
        self._MongoDBAtlasVectorSearch = MongoDBAtlasVectorSearch

    def _collection_exists(self, collection_name: str) -> bool:
        """
        Check if a collection exists in the MongoDB database.
        Args:
            collection_name (str): The name of the collection to check.
        Returns:
            bool: True if the collection exists, False otherwise.
        """
        return collection_name in self.db.list_collection_names()

    def _create_collection(self, collection_name: str) -> Any:
        """
        Create a new collection in the MongoDB database.
        Args:
            collection_name (str): The name of the collection to create.
        Returns:
            Collection: The created collection.
        """
        logger.info(f"🪣 Creating new collection '{collection_name}'")
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
        if not self._collection_exists(collection_name):
            logger.warning(f"∅ Collection '{collection_name}' not found!")
            raise CollectionNotFoundError(collection_name)

        logger.debug(f"🗳️  Collection '{collection_name}' exists!")

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
        index_filters: list[str] = DEFAULT_INDEX_FIELDS,
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
        # Filter out potentially problematic fields by analyzing the collection
        safe_filters = self._get_safe_filter_fields(collection_name, index_filters)

        if len(safe_filters) < len(index_filters):
            logger.info(
                f"🔧 Using {len(safe_filters)}/{len(index_filters)} "
                "safe filter fields for index creation"
            )

        # Get the vector store for the collection
        store = self._get_vector_store(
            collection_name=collection_name, vector_index_name=vector_index_name
        )
        if not self._index_exists(collection_name, vector_index_name):
            logger.info(
                f"🪣 Creating index '{vector_index_name}' with filters: {safe_filters}"
            )
            vec_dimensions, similarity = embedding_model_info(self.embedding_model)
            store.create_vector_search_index(
                dimensions=vec_dimensions,
                path="embedding",
                similarity=similarity,
                filters=safe_filters,
            )
            logger.info("✅ Index created successfully.")
        else:
            logger.warning(f"Index '{vector_index_name}' already exists")

        storage_context = StorageContext.from_defaults(vector_store=store)
        return VectorStoreIndex.from_vector_store(
            store, embed_model=self.embedding_model, storage_context=storage_context
        )

    def _get_index_filters(self, collection_name: str, index_name: str) -> list[str]:
        """Retrieve the filters for a given index name in a collection."""
        indexes = self._get_collection(collection_name).list_search_indexes()
        for index in indexes:
            if index.get("name") == index_name:
                return index.get("definition", {}).get("fields", [])
        return []

    def _drop_index(self, collection_name: str, index_name: str):
        """Drop the specified index from the collection."""
        col = self._get_collection(collection_name)
        col.drop_search_index(index_name)
        logger.info(
            f"🗑️ Dropped index '{index_name}' from collection '{collection_name}'"
        )

    def _needs_filter_update(
        self,
        collection_name: str,
        vector_index_name: str,
        desired_filters: list[str],
    ) -> tuple[bool, list[str]]:
        """Check if the vector search index needs filter updates.

        Compares the current index filters with the desired filters and determines
        if an update is needed.

        Args:
            collection_name (str): The name of the collection containing the index.
            vector_index_name (str): The name of the vector search index.
            desired_filters (list[str]): The desired filter fields for the index.

        Returns:
            tuple[bool, list[str]]: A tuple containing:
                - bool: True if update is needed, False otherwise
                - list[str]: List of missing filters that need to be added
        """
        current_filters = self._get_index_filters(collection_name, vector_index_name)

        # Flatten current_filters if it's a list of dicts, otherwise use as is
        if current_filters and isinstance(current_filters[0], dict):
            current_filters = [
                f.get("path")
                for f in current_filters
                if isinstance(f, dict) and f.get("path")
            ]

        # Find missing filters
        missing_filters = [f for f in desired_filters if f not in current_filters]

        return bool(missing_filters), missing_filters

    def _update_index_filters(
        self,
        collection_name: str,
        vector_index_name: str,
        new_filters: list[str],
    ) -> VectorStoreIndex:
        """Update an existing vector search index with additional filter fields.

        Since PyMongo doesn't support updating vector search indexes directly,
        this method drops the existing index and recreates it with both the
        existing filters and the new filters combined.

        Args:
            collection_name (str): The name of the collection containing the index.
            vector_index_name (str): The name of the vector search index to update.
            new_filters (list[str]): The additional filter fields to add to the existing ones.

        Returns:
            VectorStoreIndex: The newly created index with combined filters.

        Note:
            This operation will temporarily make the index unavailable during the
            drop-and-recreate process.
        """
        # Get current filters to preserve them
        current_filters = self._get_index_filters(collection_name, vector_index_name)

        # Flatten current_filters if it's a list of dicts
        if current_filters and isinstance(current_filters[0], dict):
            current_filters = [
                f.get("path")
                for f in current_filters
                if isinstance(f, dict) and f.get("path")
            ]

        # Ensure current_filters is a list of strings (filter out None values)
        current_filters = [f for f in current_filters if f is not None]

        # Combine existing and new filters, removing duplicates while preserving order
        combined_filters = list(dict.fromkeys(current_filters + new_filters))

        logger.info(
            f"🔄 Updating index '{vector_index_name}' with combined filter fields: "
            f"{combined_filters}"
        )

        # Drop the existing index
        self._drop_index(collection_name, vector_index_name)

        # Recreate with combined filters
        return self._create_index(
            collection_name=collection_name,
            vector_index_name=vector_index_name,
            index_filters=combined_filters,
        )

    def get_index(
        self, collection_name: str, create_if_not_exists: bool = False, **kwargs
    ):
        vector_index_name = kwargs.get(
            "vector_index_name", settings.MONGO_VECTOR_INDEX_NAME
        )
        logger.debug(f"🔍 Getting index for collection {collection_name}")

        # Check the collection exists
        if not self._collection_exists(collection_name):
            if create_if_not_exists:
                self._create_collection(collection_name=collection_name)
            else:
                raise CollectionNotFoundError(collection_name)

        index_filters = kwargs.get("index_filters", self.DEFAULT_INDEX_FIELDS)

        if not self._index_exists(collection_name, vector_index_name):
            logger.warning("🗂️  Non existing / Empty Index!")
            if create_if_not_exists:
                return self._create_index(
                    collection_name=collection_name,
                    vector_index_name=vector_index_name,
                    index_filters=index_filters,
                )
            else:
                raise VectorStoreIndexNotFoundError(
                    collection_name=collection_name, index_name=vector_index_name
                )
        else:
            # Index exists, check if filters need to be updated
            needs_update, missing_filters = self._needs_filter_update(
                collection_name, vector_index_name, index_filters
            )
            if needs_update:
                # NOTE: We don't update the index filters automatically
                # because it requires dropping and recreating the index,
                # which can be disruptive.
                logger.warning(f"🆕 Found new filters to add: {missing_filters}")
                # return self._update_index_filters(
                #     collection_name=collection_name,
                #     vector_index_name=vector_index_name,
                #     new_filters=missing_filters,
                # )

        store = self._get_vector_store(
            collection_name=collection_name, vector_index_name=vector_index_name
        )
        index = VectorStoreIndex.from_vector_store(
            store, embed_model=self.embedding_model
        )
        logger.info("✅ Index loaded successfully.")
        return index

    def get_docs(
        self,
        collection_name: str,
        filters: dict[str, Any],
        **kwargs: Any,
    ) -> list[dict] | None:
        """
        Get a document's vector by its ID from the specified collection.
        Args:
            collection_name (str): The name of the collection to get the document from.
            doc_id (str): The ID of the document to retrieve.
        Returns:
            list[dict]: The document with the specified ID, or None if not found.
        """
        col = self._get_collection(collection_name)
        return list(col.find(filters))

    def delete_docs(
        self, collection_name: str, filters: dict[str, Any], **kwargs
    ) -> None:
        """
        Delete a document's vectors by its ID from the specified collection.
        Args:
            collection_name (str): The name of the collection to delete the document from.
            doc_id (str): The ID of the document to delete.
        """
        col = self._get_collection(collection_name)
        result = col.delete_many(filters)
        if result.deleted_count == 0:
            logger.warning(
                f"No document found with filters '{filters}' "
                f"in collection '{collection_name}'."
            )
        else:
            logger.info(
                f"🗑️ Deleted document with filters '{filters}' "
                f"from collection '{collection_name}'."
            )

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

    def _get_safe_filter_fields(
        self, collection_name: str, desired_filters: list[str]
    ) -> list[str]:
        """Get filter fields that are safe to use based on document analysis.

        This method analyzes a sample of documents in the collection to determine
        which metadata fields are commonly present and safe to use for filtering.

        Args:
            collection_name (str): The name of the collection to analyze
            desired_filters (list[str]): The desired filter fields

        Returns:
            list[str]: Filter fields that are safe to use (present in most documents)
        """
        try:
            collection = self._get_collection(collection_name)

            # Get a sample of documents to check field presence
            sample_size = min(50, collection.estimated_document_count())
            if sample_size == 0:
                logger.warning(
                    f"📭 Collection '{collection_name}' is empty, "
                    "using all desired filters"
                )
                return desired_filters

            sample_docs = list(
                collection.aggregate([{"$sample": {"size": sample_size}}])
            )

            if not sample_docs:
                logger.warning(
                    f"📭 No documents sampled from '{collection_name}', using all desired filters"
                )
                return desired_filters

            # Check field presence in sample
            field_counts = {field: 0 for field in desired_filters}

            for doc in sample_docs:
                for field in desired_filters:
                    # Navigate nested fields (e.g., "metadata.supabase_id")
                    field_parts = field.split(".")
                    current_value = doc

                    try:
                        for part in field_parts:
                            current_value = current_value[part]

                        # If we got here, field exists and is not None
                        if current_value is not None:
                            field_counts[field] += 1
                    except (KeyError, TypeError):
                        # Field is missing or path is invalid
                        pass

            # Keep fields that are present in at least 50% of documents
            threshold = len(sample_docs) * 0.5
            safe_fields = []

            for field, count in field_counts.items():
                percentage = (count / len(sample_docs)) * 100 if sample_docs else 0
                if count >= threshold:
                    safe_fields.append(field)
                    logger.debug(
                        f"✅ Field '{field}' is safe: {count}/{len(sample_docs)} ({percentage:.1f}%)"
                    )
                else:
                    logger.warning(
                        f"⚠️ Field '{field}' is sparse: {count}/{len(sample_docs)} ({percentage:.1f}%) - excluding from index"
                    )

            if len(safe_fields) < len(desired_filters):
                excluded = set(desired_filters) - set(safe_fields)
                logger.info(f"🔧 Excluded sparse filter fields: {excluded}")

            return safe_fields

        except Exception as e:
            logger.warning(
                f"⚠️ Could not analyze field safety for '{collection_name}': {e}"
            )
            logger.info("🔄 Falling back to core essential fields only")

            # Return only the most essential fields as fallback
            essential_fields = [
                "metadata.doc_id",
                "metadata.client_id",
                "metadata.llm_backend",
                "metadata.embedding_model",
            ]
            return [field for field in essential_fields if field in desired_filters]

    # ...existing code...


class ChromaVectorStore(VectorStore):
    def __init__(
        self,
        embedding_model: BaseEmbedding,
        host: str = settings.CHROMA_HOST,
        port: int = settings.CHROMA_PORT,
    ):
        """Initialize the ChromaDB vector store client.

        Args:
            embedding_model (BaseEmbedding): Embedding model instance to use for vectorization.
            host (str, optional): ChromaDB host URL.
                Defaults to settings.CHROMA_HOST.
            port (int, optional): ChromaDB port number.
                Defaults to settings.CHROMA_PORT.
        """
        import chromadb
        from llama_index.vector_stores.chroma import ChromaVectorStore as CVS

        self.embedding_model = embedding_model
        self.db = chromadb.HttpClient(host, int(port))
        logger.info(f"🔌 Connected to ChromaDB at {host}:{port}")
        self._CVS = CVS

    def _collection_exists(self, collection_name: str) -> bool:
        """Check if a collection exists in the ChromaDB database.

        Args:
            collection_name (str): Name of the collection to check.

        Returns:
            bool: True if the collection exists, False otherwise.
        """
        return collection_name in self.db.list_collections()

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
        if self._collection_exists(collection_name):
            raise ValueError(f"💥 Collection {collection_name} already exists!")

        # Get the embedding function based on the embed model
        embed_model_name = self.embedding_model.model_name
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
        try:
            chroma_collection = self.db.get_collection(collection_name)
        except ValueError as e:
            logger.warning(f"∅ Error getting collection '{collection_name}': {e}")
            raise CollectionNotFoundError(collection_name)

        if count := chroma_collection.count():
            logger.info(
                f"🗳️ Collection {collection_name} exists! (Total vectors: {count})"
            )

        return chroma_collection

    def _get_vector_store(self, collection_name: str, **kwargs: Any):
        logger.debug(f"🔍 Getting vector store for collection {collection_name}")
        col = self.db.get_collection(collection_name)
        return self._CVS(chroma_collection=col, embed_model=self.embedding_model)

    def _index_exists(self, collection_name: str, **kwargs) -> bool:
        """
        Check if the index exists (i.e.: if the collection exists).
        Args:
            collection_name (str): The name of the collection to check.
        Returns:
            bool: True if the index exists, False otherwise.
        """
        return self._collection_exists(collection_name)

    def _create_index(self, collection_name: str, **kwargs):
        """Creating a vector index in ChromaDB is really just creating a collection.
        This method checks if the collection already exists, and if not, creates it
        with the specified embedding model and similarity function.
        """
        self._create_collection(collection_name=collection_name, **kwargs)

    def get_index(
        self, collection_name: str, create_if_not_exists: bool = False, **kwargs
    ):
        logger.debug(f"🔍 Getting index for collection {collection_name}")

        if not self._index_exists(collection_name):
            if create_if_not_exists:
                logger.info(
                    f"✨ Collection {collection_name} does not exist! "
                    "Creating a new collection."
                )
                self._create_collection(collection_name=collection_name)
            else:
                raise CollectionNotFoundError(collection_name=collection_name)

        vector_store = self._get_vector_store(collection_name)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        return VectorStoreIndex.from_vector_store(
            vector_store,
            embed_model=self.embedding_model,
            storage_context=storage_context,
        )

    def get_docs(
        self,
        collection_name: str,
        filters: dict[str, Any],
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
        return col.get(where=filters, include=include).get("metadatas")

    def delete_docs(
        self, collection_name: str, filters: dict[str, Any], **kwargs
    ) -> None:
        """
        Delete a document by its ID from the specified collection in ChromaDB.
        Args:
            collection_name (str): The name of the collection to delete the document from.
            doc_id (str): The ID of the document to delete.
        """
        col = self.db.get_collection(collection_name)
        try:
            col.delete(where=filters)
            logger.info(
                f"🗑️ Deleted document with filters '{filters}' "
                f"from collection '{collection_name}'."
            )
        except Exception as e:
            logger.warning(
                f"Failed to delete documents with filters '{filters}' "
                f"from collection '{collection_name}': {e}"
            )

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


def get_vector_store(
    store_backend: str, embedding_model: BaseEmbedding, **kwargs
) -> VectorStore:
    """Vector store factory function.
    This function returns an instance of a vector store based on the specified backend.
    Supported backends are 'mongo' and 'chroma'.

    Args:
        store_backend (str): The vector store backend to use. One of 'mongo' or 'chroma'.
        embedding_model (BaseEmbedding): The **embedding model instance** to use for vectorization.
        **kwargs: Additional keyword arguments to pass to the vector store constructor.

    Raises:
        ValueError: If the specified vector store backend is not supported.

    Returns:
        VectorStore: An instance of the specified vector store backend.
    """
    if store_backend.lower() == VectorStoreBackend.MONGO:
        return MongoVectorStore(embedding_model, **kwargs)
    elif store_backend.lower() == VectorStoreBackend.CHROMA:
        return ChromaVectorStore(embedding_model, **kwargs)
    else:
        raise ValueError(f"Unknown vector store backend: {store_backend}")


def get_default_vector_collection_name(
    vector_store_backend: str,
    client_id: str | None = None,
    llm_backend: str | None = None,
    embedding_model_id: str | None = None,
) -> str:
    """Returns the default vector collection name based on the environment.
    In MongoDB, we use a single collection for all clients, while in ChromaDB
    we use a collection per client and LLM backend.
    The collection name is determined by the VECTOR_STORE_BACKEND setting.
    """
    if vector_store_backend == VectorStoreBackend.MONGO:
        return settings.MONGO_VECTOR_COLLECTION
    elif vector_store_backend == VectorStoreBackend.CHROMA:
        if settings.CHROMA_COLLECTION:
            return settings.CHROMA_COLLECTION
        else:
            if not client_id or not llm_backend or not embedding_model_id:
                raise ValueError(
                    "💥 For ChromaDB, client_id, llm_backend, and embedding_model "
                    "must be provided if the CHROMA_COLLECTION setting is not set."
                )
            return f"{client_id}-{llm_backend}-{embedding_model_id}"
    else:
        raise ValueError(
            f"💥 Unsupported vector store backend: {vector_store_backend}. "
            "Supported backends are 'mongo' and 'chroma'."
        )
