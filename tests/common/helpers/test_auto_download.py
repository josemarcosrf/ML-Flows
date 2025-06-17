from pathlib import Path

import pytest

from flows.common.helpers.auto_download import download_if_remote, is_url


# Mock functions for downloading
def mock_download_from_s3(path):
    return Path("/mock/local/s3/file")


def mock_download_from_url(path):
    return Path("/mock/local/url/file")


# Apply the mocks
@pytest.fixture(autouse=True)
def apply_mocks(monkeypatch):
    monkeypatch.setattr(
        "flows.common.helpers.auto_download.download_from_s3", mock_download_from_s3
    )
    monkeypatch.setattr(
        "flows.common.helpers.auto_download.download_from_url", mock_download_from_url
    )


@pytest.mark.parametrize(
    "url,expected",
    [
        ("http://example.com/file.txt", True),
        ("https://example.com/file.txt", True),
        ("s3://bucket/key", False),
        ("/local/path", False),
    ],
)
def test_is_url(url, expected):
    assert is_url(url) == expected


@download_if_remote(include=["file_path"])
def process_file_include(file_path: str, a: str, b: str, *args, **kwargs):
    return file_path, a, b


@download_if_remote(exclude=["file_path"])
def process_file_exclude(file_path: str, a: str, b: str, *args, **kwargs):
    return file_path, a, b


def test_download_if_remote_with_include():
    remote_path = "http://example.com/remote/file"
    local_path, a, b = process_file_include(file_path=remote_path, a=remote_path, b="1")
    assert local_path == "/mock/local/url/file"
    assert a == remote_path  # should be unchanged
    assert b == "1"  # should be unchanged


def test_download_if_remote_with_exclude():
    remote_path = "http://example.com/remote/file"
    expected_local_path = "/mock/local/url/file"

    # Should only modify 'a' and 'b' and not 'file_path'
    local_path, a, b = process_file_exclude(remote_path, a=remote_path, b="1")
    assert local_path == remote_path  # should be unchanged
    assert a == expected_local_path  # should be changed (not excluded)
    assert b == "1"  # should be unchanged (not a remote path)


def test_download_if_remote_with_include_list():
    remote_paths = [
        "http://example.com/remote/file1",
        "http://example.com/remote/file2",
    ]
    expected_local_path = "/mock/local/url/file"

    # Should only modify 'file_path' and not 'a' or 'b'
    local_paths, a, b = process_file_include(
        file_path=remote_paths, a=remote_paths[0], b=remote_paths
    )
    assert local_paths == [expected_local_path, expected_local_path]
    assert a == remote_paths[0]
    assert b == remote_paths


def test_download_if_remote_with_exclude_list():
    remote_paths = [
        "http://example.com/remote/file1",
        "http://example.com/remote/file2",
    ]
    expected_local_path = "/mock/local/url/file"

    # Should only modify 'a' and 'b' and not 'file_path'
    local_paths, a, b = process_file_exclude(
        file_path=remote_paths, a=remote_paths[0], b=remote_paths
    )
    assert local_paths == remote_paths
    assert a == expected_local_path
    assert b == [expected_local_path] * 2


def test_download_if_remote_with_include_dict():
    remote_paths = {
        "file1": "http://example.com/remote/file1",
        "file2": "http://example.com/remote/file2",
    }
    (
        local_paths,
        a,
        b,
    ) = process_file_include(file_path=remote_paths, a="a", b="b")
    assert local_paths == remote_paths  # Unchanged as it doesn't support dict
    assert a == "a"
    assert b == "b"


def test_download_if_remote_raises_on_invalid_path():
    # Should raise Exception if download_from_url fails (simulate by raising in the mock)
    def fail_download_from_url(path):
        raise Exception("💥 Error downloading from URL: fail")

    # Patch only download_from_url to raise
    import importlib

    from flows.common.helpers import auto_download as ad

    importlib.reload(ad)

    @ad.download_if_remote(include=["file_path"])
    def proc(file_path):
        return file_path

    # Patch download_from_url to raise

    orig = ad.download_from_url
    ad.download_from_url = fail_download_from_url
    try:
        with pytest.raises(Exception, match="💥 Error downloading from URL: fail"):
            proc("http://example.com/remote/file")
    finally:
        ad.download_from_url = orig
