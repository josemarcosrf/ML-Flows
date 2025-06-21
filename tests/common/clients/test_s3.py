import pytest

from flows.common.helpers import s3


@pytest.mark.parametrize(
    "uri,expected",
    [
        ("s3://bucket/key", True),
        ("not-a-s3-uri", False),
    ],
)
def test_is_valid_s3_uri(uri, expected):
    assert s3.is_valid_s3_uri(uri) == expected


@pytest.mark.parametrize(
    "path,expected",
    [
        ("s3://bucket/key", True),
        ("/local/path", False),
        ("https://bucket.s3.amazonaws.com/key", True),
    ],
)
def test_is_s3_path(path, expected):
    assert s3.is_s3_path(path) == expected


@pytest.mark.parametrize(
    "uri,expected_bucket,expected_key",
    [
        ("s3://bucket/key/path.txt", "bucket", "key/path.txt"),
        # ("https://bucket.s3.amazonaws.com/key/path.txt", "bucket", "key/path.txt"),
    ],
)
def test_parse_s3_uri_valid(uri, expected_bucket, expected_key):
    bucket, key = s3.parse_s3_uri(uri)
    assert bucket == expected_bucket
    assert key == expected_key


@pytest.mark.parametrize(
    "uri",
    [
        "not-a-s3-uri",
    ],
)
def test_parse_s3_uri_invalid(uri):
    with pytest.raises(ValueError):
        s3.parse_s3_uri(uri)
