import pytest

from flows.preproc import index_document_file


@pytest.mark.parametrize("extension", ["txt", "pdf"])
def test_index_document_file_mocks(mocker, tmp_path, extension):
    # Create dummy file with the given extension
    file_path = tmp_path / f"dummy.{extension}"
    file_path.write_text("This is a test document.")
    dummy_file = str(file_path)

    # Patch the pub_and_log function
    pub_mock = mocker.MagicMock()
    mocker.patch("flows.preproc.pub_and_log", return_value=pub_mock)

    # Patch the MongoDB client and its methods
    db_mock = mocker.MagicMock()
    mocker.patch("flows.preproc.MongoDBClient", return_value=db_mock)
    db_mock.update_one.return_value = {"acknowledged": True}

    # Patch the get_default_vector_collection_name function
    mocker.patch(
        "flows.preproc.get_default_vector_collection_name",
        return_value="test_collection",
    )

    # Patch docling_2_md.submit(...).result() for PDF files
    docling_2_md_submit_mock = mocker.patch("flows.preproc.index.docling_2_md.submit")
    if extension == "pdf":
        docling_2_md_result_mock = mocker.MagicMock()
        docling_2_md_result_mock.result.return_value = "This is a test document."
        docling_2_md_submit_mock.return_value = docling_2_md_result_mock

    # Patch the index_document task
    index_document_mock = mocker.patch("flows.preproc.index.index_document.submit")
    index_document_mock.return_value.result.return_value = 1

    # Call the Flow with the dummy file
    result = index_document_file(
        client_id="test_client",
        file_path=dummy_file,
        embedding_model="test-embedding",
        chunk_size=128,
        chunk_overlap=16,
        llm_backend="test-llm",
        vector_store_backend="mongo",
        pubsub=False,
        metadata={"name": f"dummy.{extension}"},
    )

    assert result is None
    db_mock.update_one.assert_called()
    pub_mock.assert_called()
    if extension == "pdf":
        docling_2_md_submit_mock.assert_called_once_with(dummy_file)
    else:
        docling_2_md_submit_mock.assert_not_called()
    index_document_mock.assert_called()
