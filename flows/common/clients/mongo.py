from typing import Any

from loguru import logger
from pymongo import MongoClient

from flows.settings import settings


class MongoDBClient:
    """
    A client for MongoDB operations, including insertions and updates.
    This client is designed to work with MongoDB Atlas and supports basic CRUD operations.
    """

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
