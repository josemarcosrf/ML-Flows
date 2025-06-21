from flows.common.helpers import noop, sanitize_uri


def test_sanitize_uri_removes_password():
    uri = "mongodb://user:secret@localhost:27017/db"
    sanitized = sanitize_uri(uri)
    assert "secret" not in sanitized
    assert "<PWD>" in sanitized


def test_noop():
    assert noop() is None
    assert noop(1, 2, a=3) is None
