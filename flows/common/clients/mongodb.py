from typing import Any

from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.mongodb import MongoDBAtlasVectorSearch
from loguru import logger
from pymongo import MongoClient
from tabulate import tabulate

from flows.common.clients.llms import embedding_model_info
from flows.settings import settings


def index_exists(collection, index_name):
    indexes = collection.list_search_indexes()
    for index in indexes:
        if index.get("name") == index_name:
            return True
    return False


class MongoDBClient:
    DEFAULT_VECTOR_INDEX_NAME = "vector_index"

    def __init__(self, uri: str = settings.MONGO_URI, db_name: str = settings.MONGO_DB):
        logger.info(f"🔌 Initializing MongoDB connection {uri} | DB:{db_name}")
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        try:
            # The ismaster command is cheap and does not require auth.
            self.client.admin.command("ismaster")
            logger.info("✅ MongoDB connection established successfully")
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            raise e

    def get_vector_store(
        self,
        collection_name: str = settings.MONGO_DOC_COLLECTION,
        vector_index_name: str = DEFAULT_VECTOR_INDEX_NAME,
    ) -> MongoDBAtlasVectorSearch:
        """
        Initialize the vector index based on the specified backend and models.
        Args:
            collection_name (str): The name of the MongoDB collection.
            vector_index_name (str): The name of the vector index.
        Returns:
            MongoDBAtlasVectorSearch: The MongoDB vector store.
        """
        # Create the MongoDB vector store
        logger.debug(f"🔍 Getting vector store for collection {collection_name}")
        return MongoDBAtlasVectorSearch(
            self.client,
            db_name=self.db.name,
            collection_name=collection_name,
            vector_index_name=vector_index_name,
        )

    def create_index(
        self,
        embed_model,
        collection_name: str = settings.MONGO_DOC_COLLECTION,
        vector_index_name: str = DEFAULT_VECTOR_INDEX_NAME,
        index_filters: list[str] = ["name", "subdir"],
    ) -> VectorStoreIndex:
        """
        Initialize the vector index based on the specified backend and models.
        Args:
            llm_backend (LLMBackend): The LLM backend to use (e.g., OpenAI, Ollama).
            llm_model_name (str): The name of the LLM model to use.
            embedding_model_name (str): The name of the embedding model to use.
            documents (list[Document]): The list of documents to index.
        Returns:
            VectorStoreIndex: The initialized vector store index.
        """
        vec_dimensions, similarity = embedding_model_info(embed_model)

        # Create the MongoDB vector store
        store = self.get_vector_store(
            collection_name=collection_name,
            vector_index_name=vector_index_name,
        )
        if not index_exists(store.collection, vector_index_name):
            logger.info(f"🪣 Creating index '{vector_index_name}'")
            store.create_vector_search_index(
                dimensions=vec_dimensions,
                path="embedding",
                similarity=similarity,
                filters=index_filters,
            )
            logger.info("✅ Index created successfully.")
            # storage_context = StorageContext.from_defaults(vector_store=store)
        else:
            logger.warning(f"Index '{vector_index_name}' already exists")

        # Create the index
        return VectorStoreIndex.from_vector_store(store, embed_model=embed_model)

    def get_index(
        self,
        embed_model,
        collection_name: str = settings.MONGO_DOC_COLLECTION,
        vector_index_name: str = DEFAULT_VECTOR_INDEX_NAME,
    ) -> VectorStoreIndex:
        """
        Initialize the vector index based on the specified backend and models.
        Args:
            embed_model: The embedding model to use.
            collection_name (str): The name of the MongoDB collection.
            vector_index_name (str): The name of the vector index.
        Returns:
            VectorStoreIndex: The vector index.
        """
        store = self.get_vector_store(
            collection_name=collection_name,
            vector_index_name=vector_index_name,
        )

        if not index_exists(store.collection, vector_index_name):
            logger.warning("💥 Non existing / Empty Index!")
            raise ValueError(
                f"❌ Vector index '{vector_index_name}' does not exist "
                f"in collection '{collection_name}'. "
                "Please ensure the index is created and populated with data."
            )

        # Create the index
        index = VectorStoreIndex.from_vector_store(store, embed_model=embed_model)
        logger.info("✅ Index loaded successfully.")

        return index

    def insert_one(self, collection_name: str, document: dict[str, Any]) -> str:
        collection = self.db[collection_name]
        result = collection.insert_one(document)
        return str(result.inserted_id)

    def insert_many(
        self, collection_name: str, documents: list[dict[str, Any]]
    ) -> list[str]:
        collection = self.db[collection_name]
        result = collection.insert_many(documents)
        return [str(oid) for oid in result.inserted_ids]

    def update_one(
        self,
        collection_name: str,
        filter: dict[str, Any],
        update: dict[str, Any],
        upsert: bool = False,
    ) -> dict[str, Any]:
        collection = self.db[collection_name]
        result = collection.update_one(filter, {"$set": update}, upsert=upsert)
        return {
            "matched_count": result.matched_count,
            "modified_count": result.modified_count,
            "upserted_id": str(result.upserted_id) if result.upserted_id else None,
        }

    def print_collection_contents(
        self,
        collection_name: str = settings.MONGO_DOC_COLLECTION,
        metadata_fields: list[str] = ["doc_id", "subdir", "name"],
    ) -> None:
        """
        This function retrieves all documents from the specified collection and
        displays their metadata in a formatted table.

        Args:
            collection_name (str): The name of the MongoDB collection to inspect.
        Returns:
            None: This function prints the collection contents to the console.
        """

        store = self.get_vector_store(
            collection_name=collection_name,
            vector_index_name="vector_index",
        )

        col = store.collection

        def get_cols(doc):
            meta = doc.get("metadata", {})
            return tuple(meta.get(k, "n/d") for k in metadata_fields)

        items = list(col.find())

        if total_count := len(items):
            print(f"Total items in collection '{col.name}': {total_count} ")
            docs = {get_cols(item) for item in items}
            print(
                tabulate(docs, headers=["ID", "Subdir", "Name"], tablefmt="fancy_grid")
            )
        else:
            print("👀 No documents found!")
