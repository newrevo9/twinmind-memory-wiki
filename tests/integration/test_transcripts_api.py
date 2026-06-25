from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_create_transcript_returns_201(client):
    with patch("app.api.transcripts.create_pool") as mock_pool:
        mock_pool.return_value = AsyncMock(
            enqueue_job=AsyncMock(return_value=MagicMock(job_id="job-abc"))
        )
        resp = await client.post("/transcripts", json={"content": "Alice is my manager."})

    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["status"] == "pending"
    assert data["content"] == "Alice is my manager."
    assert data["job_id"] == "job-abc"


@pytest.mark.asyncio
async def test_create_transcript_persisted(client):
    with patch("app.api.transcripts.create_pool") as mock_pool:
        mock_pool.return_value = AsyncMock(
            enqueue_job=AsyncMock(return_value=MagicMock(job_id="job-1"))
        )
        create_resp = await client.post("/transcripts", json={"content": "Test content"})

    tid = create_resp.json()["id"]
    get_resp = await client.get(f"/transcripts/{tid}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == tid
    assert get_resp.json()["content"] == "Test content"


@pytest.mark.asyncio
async def test_get_transcript_not_found(client):
    resp = await client.get("/transcripts/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_transcript_empty_content_rejected(client):
    resp = await client.post("/transcripts", json={"content": "   "})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_transcript_missing_body_rejected(client):
    resp = await client.post("/transcripts", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_transcript_survives_redis_failure(client):
    with patch("app.api.transcripts.create_pool", side_effect=Exception("redis down")):
        resp = await client.post("/transcripts", json={"content": "Some transcript"})

    # Transcript is saved even if job enqueue fails
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending"
