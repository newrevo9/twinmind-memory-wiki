from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.services.storage import get_object, grep_objects, list_objects, object_exists, put_object


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": ""}}, "op")


@pytest.fixture
def s3(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("app.services.storage._client", lambda: mock)
    return mock


def test_put_object_strips_leading_slash(s3):
    put_object("/people/alice.md", "# Alice")
    s3.put_object.assert_called_once()
    assert s3.put_object.call_args[1]["Key"] == "people/alice.md"
    assert s3.put_object.call_args[1]["Body"] == b"# Alice"


def test_get_object_returns_decoded_content(s3):
    s3.get_object.return_value = {"Body": MagicMock(read=lambda: b"# Alice")}
    assert get_object("/people/alice.md") == "# Alice"


def test_get_object_returns_none_on_missing(s3):
    s3.get_object.side_effect = _client_error("NoSuchKey")
    assert get_object("/people/missing.md") is None


def test_get_object_reraises_other_errors(s3):
    s3.get_object.side_effect = _client_error("AccessDenied")
    with pytest.raises(ClientError):
        get_object("/people/secret.md")


def test_object_exists_true(s3):
    assert object_exists("/people/alice.md") is True


def test_object_exists_false(s3):
    s3.head_object.side_effect = _client_error("404")
    assert object_exists("/people/missing.md") is False


def test_list_objects_returns_files_and_dirs(s3):
    s3.list_objects_v2.return_value = {
        "CommonPrefixes": [{"Prefix": "people/"}],
        "Contents": [
            {"Key": "topics/python.md", "Size": 200, "LastModified": MagicMock(isoformat=lambda: "2024-01-01T00:00:00")}
        ],
    }
    entries = list_objects("/")
    dirs = [e for e in entries if e["type"] == "directory"]
    files = [e for e in entries if e["type"] == "file"]
    assert len(dirs) == 1 and dirs[0]["name"] == "people"
    assert len(files) == 1 and files[0]["name"] == "python.md"


def test_grep_returns_matching_lines(s3, monkeypatch):
    paginator = MagicMock()
    paginator.paginate.return_value = [
        {"Contents": [{"Key": "people/alice.md"}]}
    ]
    s3.get_paginator.return_value = paginator

    monkeypatch.setattr(
        "app.services.storage.get_object",
        lambda key: "# Alice\n\n- Alice is a Python expert\n- She works remotely",
    )

    matches = grep_objects("Python", "/")
    assert len(matches) == 1
    assert matches[0]["line_number"] == 3
    assert "Python" in matches[0]["line"]


def test_grep_ignores_non_md_files(s3, monkeypatch):
    paginator = MagicMock()
    paginator.paginate.return_value = [
        {"Contents": [{"Key": "people/data.json"}]}
    ]
    s3.get_paginator.return_value = paginator
    matches = grep_objects("Python", "/")
    assert matches == []
