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


def test_playbook_from_json_file(tmp_path):
    # Dummy playbook data
    data = {
        "id": "pb1",
        "name": "Test Playbook",
        "definition": {"attr1": {"question": "A Question", "valid_answers": ["a1"]}},
        "metadata": {"foo": "bar"},
    }

    # Create a temporary JSON file with playbook data
    file = tmp_path / "playbook.json"
    file.write_text(json.dumps(data))

    # Create Playbook instance from JSON file
    pb = Playbook.from_json_file(file)

    assert pb.id == "pb1"
    assert pb.name == "Test Playbook"
    assert pb.definition["attr1"]["question"] == "A Question"
    assert pb.metadata["foo"] == "bar"


def test_playbook_definition_accepts_list_of_objects():
    definitions = [
        {"attribute": "attrA", "question": "First question", "valid_answers": ["a1"]},
        {"attribute": "attrB", "question": "Second question", "valid_answers": ["a2"]},
        {"attribute": "attrC", "question": "Third question", "valid_answers": ["a3"]},
    ]
    pb = Playbook(id="pb2", name="Tuple Playbook", definition=definitions)

    assert isinstance(pb.definition, dict)
    assert list(pb.definition.keys()) == ["attrA", "attrB", "attrC"]
    assert pb.definition["attrB"]["question"] == "Second question"


def test_playbook_definition_accepts_dict_and_preserves_order():
    definitions = {
        "attrA": {"question": "A question", "valid_answers": ["aA"]},
        "attrB": {"question": "B question", "valid_answers": ["aB"]},
        "attrC": {"question": "C question", "valid_answers": ["aC"]},
    }
    pb = Playbook(id="pb3", name="Dict Playbook", definition=definitions)

    assert isinstance(pb.definition, dict)
    assert list(pb.definition.keys()) == ["attrA", "attrB", "attrC"]
    assert pb.definition["attrB"]["question"] == "B question"
