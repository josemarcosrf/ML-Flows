import os

import pytest
from pymongo import MongoClient

from flows.common.clients.llms import get_embedding_model
from flows.common.clients.vector_stores import MongoVectorStore

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
TEST_DB = "mlflows_test_db"
TEST_COLLECTION = "test_vector_collection"
TEST_INDEX = "test_vector_index"


@pytest.fixture(scope="module")
def mongo_store():
    # Use a real embedding model
    embedding_model = get_embedding_model("cohere.embed-multilingual-v3", "aws")
    mongo_store = MongoVectorStore(embedding_model, uri=MONGO_URI, db_name=TEST_DB)
    # Cleanup before and after
    client = MongoClient(MONGO_URI)
    db = client[TEST_DB]
    db.drop_collection(TEST_COLLECTION)
    yield mongo_store
    # db.drop_collection(TEST_COLLECTION)


@pytest.mark.skip(reason="Requires a real MongoDB Atlas instance; integration test.")
def test_index_and_search_fields(mongo_store):
    # Add doc1 with fields A, B
    doc1 = {
        "embedding": [0.1] * 1536,
        "metadata": {"doc_id": "doc1", "fieldA": "foo", "fieldB": "bar"},
    }
    # Add doc2 with fields A, C
    doc2 = {
        "embedding": [0.2] * 1536,
        "metadata": {"doc_id": "doc2", "fieldA": "baz", "fieldC": "qux"},
    }
    collection_name = TEST_COLLECTION
    index_filters = ["metadata.doc_id", "metadata.fieldA", "metadata.fieldB"]

    # Create index with initial filters
    mongo_store.get_index(
        collection_name,
        create_if_not_exists=True,
        index_filters=index_filters,
        vector_index_name=TEST_INDEX,
    )

    # Insert doc1
    col = mongo_store._get_collection(collection_name)
    col.insert_one(doc1)

    # Now add doc2 and update index to include fieldC
    index_filters2 = [
        "metadata.doc_id",
        "metadata.fieldA",
        "metadata.fieldB",
        "metadata.fieldC",
    ]
    mongo_store.get_index(
        collection_name,
        create_if_not_exists=False,
        index_filters=index_filters2,
        vector_index_name=TEST_INDEX,
    )
    col.insert_one(doc2)

    # Now search by all fields
    results_a = list(col.find({"metadata.fieldA": "foo"}))
    results_b = list(col.find({"metadata.fieldB": "bar"}))
    results_c = list(col.find({"metadata.fieldC": "qux"}))

    assert len(results_a) == 1 and results_a[0]["metadata"]["doc_id"] == "doc1", (
        "Expected doc1 as unique result for fieldA"
    )
    assert len(results_b) == 1 and results_b[0]["metadata"]["doc_id"] == "doc1", (
        "Expected doc1 as unique result for fieldB"
    )
    assert len(results_c) == 1 and results_c[0]["metadata"]["doc_id"] == "doc2", (
        "Expected doc2 as unique result for fieldC"
    )
