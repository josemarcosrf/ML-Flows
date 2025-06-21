from flows.common.helpers import gather_files, noop, sanitize_uri


def test_sanitize_uri_removes_password():
    uri = "mongodb://user:secret@localhost:27017/db"
    sanitized = sanitize_uri(uri)
    assert "secret" not in sanitized
    assert "<PWD>" in sanitized


def test_sanitize_uri_no_password():
    uri = "mongodb://localhost:27017/db"
    sanitized = sanitize_uri(uri)
    assert sanitized == uri


def test_gather_files_single_file(tmp_path):
    file = tmp_path / "file.txt"
    file.write_text("test")
    files = gather_files(str(file), ["*.txt"])
    assert files == [str(file)]


def test_gather_files_directory(tmp_path):
    d = tmp_path
    (d / "a.txt").write_text("a")
    (d / "b.md").write_text("b")
    files = gather_files(str(d), ["*.txt", "*.md"])
    assert set(files) == {str(d / "a.txt"), str(d / "b.md")}


def test_noop_does_nothing():
    assert noop() is None
    assert noop(1, 2, a=3) is None
