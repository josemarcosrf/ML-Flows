from typing import Any

from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.mongodb import MongoDBAtlasVectorSearch
from loguru import logger
from pymongo import MongoClient

from flows.settings import settings


def index_exists(collection, index_name):
    indexes = collection.list_search_indexes()
    for index in indexes:
        if index.get("name") == index_name:
            return True
    return False


def get_vector_store_index(
    embed_model,
    db_name: str,
    collection_name: str,
    vector_index_name: str,
    mongo_uri: str = settings.MONGO_URI,
) -> tuple[MongoDBAtlasVectorSearch, VectorStoreIndex]:
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
    # Create the MongoDB client
    mongodb_client = MongoClient(mongo_uri)

    # Create the MongoDB vector store
    store = MongoDBAtlasVectorSearch(
        mongodb_client,
        db_name=db_name,
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

    return store, index


class MongoDBClient:
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
