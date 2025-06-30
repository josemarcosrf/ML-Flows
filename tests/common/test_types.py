import json

import pytest

from flows.common.types import DBDocumentInfo, DOC_STATUS, ExportFormat, Playbook


def test_export_format_enum():
    assert ExportFormat.Markdown == "md"
    assert ExportFormat.HTML == "html"


def test_doc_status_enum():
    assert DOC_STATUS.PENDING == "pending"
    assert DOC_STATUS.INDEXING == "indexing"
    assert DOC_STATUS.INDEXED == "indexed"
    assert DOC_STATUS.FAILED == "failed"


def test_playbook_from_json_file(tmp_path):
    # Dummy playbook data
    data = {
        "id": "pb1",
        "name": "Test Playbook",
        "definition": {"step1": {"desc": "A step", "actions": ["a1"]}},
        "metadata": {"foo": "bar"},
    }

    # Create a temporary JSON file with playbook data
    file = tmp_path / "playbook.json"
    file.write_text(json.dumps(data))

    # Create Playbook instance from JSON file
    pb = Playbook.from_json_file(file)

    assert pb.id == "pb1"
    assert pb.name == "Test Playbook"
    assert pb.definition["step1"]["desc"] == "A step"
    assert pb.metadata["foo"] == "bar"


def test_document_status_validation():
    doc = DBDocumentInfo(
        id="1",
        sha1="sha1",
        name="n",
        client_id="c",
        collection="col",
        created_at="now",
        status="pending",
    )
    assert doc.status == "pending"

    with pytest.raises(ValueError):
        DBDocumentInfo(
            id="2",
            sha1="sha1",
            name="n",
            client_id="c",
            collection="col",
            created_at="now",
            status="not_a_status",
        )
