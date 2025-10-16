import importlib
import os
import time
from pathlib import Path

import pytest
from dotenv import load_dotenv
from pymongo import MongoClient

# We'll use the real MongoVectorStore but avoid requiring a vector search index
# by patching the instance get_index method. We also keep the real QAgent but
# stub its `rag` method to return schema-compliant answers so we don't call
# external LLMs during the integration test.


@pytest.mark.integration
def test_run_qa_playbook_writes_results(monkeypatch):
    repo_root = Path(__file__).resolve().parents[2]

    # Load .dev.env into environment then override MONGO_DB
    env_path = repo_root / ".dev.env"
    if not env_path.exists():
        pytest.skip(".dev.env not found in repo root")

    # Force dotenv to override any env vars set by test conftest so the
    # Mongo Atlas settings in .dev.env are used for this integration test.
    load_dotenv(env_path, override=True)
    os.environ["MONGO_DB"] = "integration-test"

    # Reload settings so the Pydantic Settings reflect the .dev.env values
    import flows.settings as settings_mod

    importlib.reload(settings_mod)
    settings = settings_mod.settings

    # Source other modules after settings have been reloaded
    import flows.shrag as shrag
    from flows.common.types import Playbook

    # Define variables / constants overrides
    CLIENT_ID = "integration-client"
    settings.MONGO_DB = "integration-test"

    # Ensure a clean test DB
    client = MongoClient(settings.MONGO_URI)
    test_db = client[str(settings.MONGO_DB)]
    # Drop collections used by the flow to start clean
    assert settings.MONGO_DB == "integration-test", "Refusing to drop non-test DB"
    test_db.drop_collection(settings.MONGO_RESULTS_COLLECTION)
    test_db.drop_collection(settings.MONGO_VECTOR_COLLECTION)

    # Build two small playbooks (one single, one hierarchical Yes/No) and run the flow
    # 1. Simple non-hierarchical playbook
    pb1 = Playbook(
        id="pb1",
        name="single",
        version=1,
        definition={
            "q1": {
                "group": "",
                "question": "Is this valid?",
                "question_type": "yes/no",
                "valid_answers": ["yes", "no"],
            }
        },
    )
    # 2. Hierarchical playbook where first question is YES/NO and should trigger
    # the follow-ups
    pb2 = Playbook(
        id="pb2",
        name="hier",
        version=1,
        definition={
            "pb2q1": {
                "group": "g",
                "question": "Is there a lease?",
                "question_type": "yes/no",
                "valid_answers": ["yes", "no"],
            },
            "pb2q2": {
                "group": "g",
                "question": "What is the term?",
                "question_type": "summarisation",
                "valid_answers": [],
            },
        },
    )

    # Create a small text document and index it using the real indexing pipeline
    # so the vector collection will contain real nodes for the QA run.
    from llama_index.core.schema import Document

    from flows.common.clients.vector_stores import get_default_vector_collection_name
    from flows.preproc.index import index_document

    # Create a small text file in tmp directory and read it (we won't call index_file.
    sample_text = (
        "This is a sample contract. The lease term is 12 months. "
        "The tenant agrees to payment."
        "The agreement was signed on 2024-01-01."
    )
    # Build a Document object (index_document.fn expects a Document)
    doc_id = "doc-integration-1"
    doc = Document(
        doc_id=doc_id,
        text=sample_text,
        extra_info={
            "name": "integration-sample",
            "llm_backend": settings.LLM_BACKEND,
            "vector_store_backend": settings.VECTOR_STORE_BACKEND,
            "embedding_model": settings.EMBEDDING_MODEL,
            "client_id": CLIENT_ID,
        },
    )

    collection_name = get_default_vector_collection_name(
        vector_store_backend=settings.VECTOR_STORE_BACKEND,
        client_id=CLIENT_ID,
        llm_backend=settings.LLM_BACKEND,
        embedding_model_id=settings.EMBEDDING_MODEL,
    )

    # Call the index task function directly (synchronous execution)
    inserted = index_document.fn(
        doc=doc,
        collection_name=collection_name,
        embedding_model_id=settings.EMBEDDING_MODEL,
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        llm_backend=settings.LLM_BACKEND,
        vector_store_backend=settings.VECTOR_STORE_BACKEND,
    )

    assert inserted > 0, "Indexing inserted zero nodes"

    # Wait a few seconds to ensure the vector store is ready
    time.sleep(5)

    # Run both playbooks sequentially against the real agent and embeddings
    _ = shrag.run_qa_playbook(client_id=CLIENT_ID, playbook=pb1, pubsub=False)
    _ = shrag.run_qa_playbook(client_id=CLIENT_ID, playbook=pb2, pubsub=False)

    # Validate that results were written to MongoDB for both playbooks
    results_col = test_db[settings.MONGO_RESULTS_COLLECTION]

    doc1 = results_col.find_one({"playbook_id": "pb1", "client_id": CLIENT_ID})
    doc2 = results_col.find_one({"playbook_id": "pb2", "client_id": CLIENT_ID})

    assert doc1 is not None, "Playbook 1 results were not written to MongoDB"
    assert doc2 is not None, "Playbook 2 results were not written to MongoDB"

    # Basic content checks
    assert "answers" in doc1
    assert len(doc1["answers"]) == 1
    assert "answers" in doc2
    assert len(doc2["answers"]) == 2
