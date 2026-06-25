from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_ls_root(client):
    with patch("app.api.memories.list_objects") as mock:
        mock.return_value = [
            {"name": "people", "path": "/people", "type": "directory", "size": None, "last_modified": None},
            {"name": "topics", "path": "/topics", "type": "directory", "size": None, "last_modified": None},
        ]
        resp = await client.get("/memories/ls")

    assert resp.status_code == 200
    data = resp.json()
    assert data["path"] == "/"
    assert len(data["entries"]) == 2
    assert data["entries"][0]["type"] == "directory"


@pytest.mark.asyncio
async def test_ls_subdirectory(client):
    with patch("app.api.memories.list_objects") as mock:
        mock.return_value = [
            {"name": "alice.md", "path": "/people/alice.md", "type": "file", "size": 300, "last_modified": "2024-01-01"},
        ]
        resp = await client.get("/memories/ls?path=/people")

    assert resp.status_code == 200
    assert resp.json()["path"] == "/people"
    assert resp.json()["entries"][0]["name"] == "alice.md"


@pytest.mark.asyncio
async def test_cat_returns_content(client):
    with patch("app.api.memories.get_object") as mock:
        mock.return_value = "# Alice\n\n- Manager"
        resp = await client.get("/memories/cat?path=/people/alice.md")

    assert resp.status_code == 200
    assert resp.json()["content"] == "# Alice\n\n- Manager"
    assert resp.json()["path"] == "/people/alice.md"


@pytest.mark.asyncio
async def test_cat_not_found(client):
    with patch("app.api.memories.get_object", return_value=None):
        resp = await client.get("/memories/cat?path=/people/missing.md")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cat_rejects_non_md_path(client):
    resp = await client.get("/memories/cat?path=/people/alice")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_grep_returns_matches(client):
    with patch("app.api.memories.grep_objects") as mock:
        mock.return_value = [
            {"path": "/people/alice.md", "line_number": 3, "line": "- Alice is a Python expert"}
        ]
        resp = await client.get("/memories/grep?pattern=Python")

    assert resp.status_code == 200
    data = resp.json()
    assert data["pattern"] == "Python"
    assert len(data["matches"]) == 1
    assert data["matches"][0]["line_number"] == 3


@pytest.mark.asyncio
async def test_grep_empty_pattern_rejected(client):
    resp = await client.get("/memories/grep?pattern=")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_grep_with_path_filter(client):
    with patch("app.api.memories.grep_objects") as mock:
        mock.return_value = []
        resp = await client.get("/memories/grep?pattern=python&path=/topics")

    assert resp.status_code == 200
    mock.assert_called_once_with("python", "/topics")
