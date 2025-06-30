from types import SimpleNamespace

import pytest

from flows.common.clients import vector_stores


class DummyCollection:
    def __init__(self):
        self.docs = []
        self.deleted = []

    def find(self, query=None):
        if query is None:
            return self.docs
        return [
            d
            for d in self.docs
            if d.get("metadata", {}).get("doc_id") == query.get("metadata.doc_id")
        ]

    def delete_many(self, query):
        to_delete = [
            d
            for d in self.docs
            if d.get("metadata", {}).get("doc_id") == query.get("metadata.doc_id")
        ]
        for d in to_delete:
            self.docs.remove(d)
        self.deleted.extend(to_delete)
        return SimpleNamespace(deleted_count=len(to_delete))

    def list_search_indexes(self):
        return [{"name": "idx"}]

    def count(self):
        return len(self.docs)


class DummyDB:
    def __init__(self):
        self.collections = {"col": DummyCollection()}

    def __getitem__(self, name):
        return self.collections[name]

    def list_collection_names(self):
        return list(self.collections.keys())

    def create_collection(self, name):
        self.collections[name] = DummyCollection()
        return self.collections[name]


class DummyClient:
    def __init__(self):
        self.db = DummyDB()


class DummyEmbed:
    model_name = "dummy"


def test_mongo_vector_store_get_and_delete_doc(monkeypatch):
    monkeypatch.setattr(
        vector_stores, "MongoVectorStore", vector_stores.MongoVectorStore
    )
    store = vector_stores.MongoVectorStore(
        DummyEmbed(), uri="mongodb://localhost", db_name="db"
    )
    store.client = DummyClient()
    store.db = store.client.db
    store.db["col"].docs = [
        {"metadata": {"doc_id": "1"}},
        {"metadata": {"doc_id": "2"}},
    ]
    docs = store.get_docs("col", filters={"metadata.doc_id": "1"})
    assert docs == [{"metadata": {"doc_id": "1"}}]
    store.delete_docs("col", filters={"metadata.doc_id": "1"})
    assert store.db["col"].docs == [{"metadata": {"doc_id": "2"}}]
    # Deleting non-existent doc
    store.delete_docs("col", filters={"doc_id": "not_found"})


@pytest.mark.skip(reason="Needs proper mocking of Chroma connection")
def test_chroma_vector_store_get_and_delete_doc(monkeypatch):
    class DummyChromaCol:
        def __init__(self):
            self.docs = {"1": {"metadatas": [{"doc_id": "1"}]}}
            self.deleted = []

        def get(self, ids, include):
            return self.docs.get(ids[0], {"metadatas": None})

        def delete(self, where):
            self.deleted.append(where)

        def count(self):
            return 1

    class DummyChromaDB:
        def get_collection(self, name):
            return DummyChromaCol()

        def list_collections(self):
            return ["col"]

    class DummyChromaStore:
        def __init__(self, *a, **k):
            pass

    monkeypatch.setattr(
        vector_stores, "ChromaVectorStore", vector_stores.ChromaVectorStore
    )
    store = vector_stores.ChromaVectorStore(DummyEmbed(), host="localhost", port=8000)
    store.db = DummyChromaDB()
    doc = store.get_docs("col", filters={"doc_id": "1"})
    assert doc == [{"doc_id": "1"}]
    store.delete_docs("col", filters={"doc_id": "1"})
