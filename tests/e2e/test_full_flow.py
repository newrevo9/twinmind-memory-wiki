"""
End-to-end tests — require all services running via docker-compose.

  docker compose up -d
  pytest tests/e2e/ -v

Skipped automatically in unit/integration runs.
"""

import asyncio
import os

import httpx
import pytest

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
SKIP = os.getenv("E2E", "").lower() not in ("1", "true")
pytestmark = pytest.mark.skipif(SKIP, reason="Set E2E=1 to run end-to-end tests")

SAMPLE_TRANSCRIPT = """
Alex: Hey, quick sync before the sprint review.
Jordan: Sure. I finished the image pipeline refactor — it's on the feature/img-pipeline branch.
Alex: Great. Did you use the new GPU queue approach we discussed?
Jordan: Yes, switched to async batch processing with Redis queues. Cut latency by 40%.
Alex: Perfect. By the way, did you know Maria joined as Staff Engineer last week? She'll own infra.
Jordan: Yeah, I met her. She's strong on Kubernetes and previously led the platform team at Stripe.
Alex: Love it. Let's make sure she reviews the pipeline PR before merge.
"""


@pytest.mark.asyncio
async def test_full_transcript_to_memory_flow():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        # 1. Health check
        health = await client.get("/health")
        assert health.status_code == 200

        # 2. Ingest transcript
        post_resp = await client.post("/transcripts", json={"content": SAMPLE_TRANSCRIPT})
        assert post_resp.status_code == 201
        transcript_id = post_resp.json()["id"]

        # 3. Poll until completed (max 60s)
        for _ in range(30):
            await asyncio.sleep(2)
            get_resp = await client.get(f"/transcripts/{transcript_id}")
            status = get_resp.json()["status"]
            if status in ("completed", "failed"):
                break

        assert status == "completed", f"Transcript status: {status}"

        # 4. ls root — should have directories
        ls_resp = await client.get("/memories/ls")
        assert ls_resp.status_code == 200
        entries = ls_resp.json()["entries"]
        assert len(entries) > 0

        # 5. grep for a known entity from the transcript
        grep_resp = await client.get("/memories/grep?pattern=Maria")
        assert grep_resp.status_code == 200
        assert len(grep_resp.json()["matches"]) > 0

        # 6. cat a memory file
        people_ls = await client.get("/memories/ls?path=/people")
        if people_ls.json()["entries"]:
            first_file = people_ls.json()["entries"][0]["path"]
            cat_resp = await client.get(f"/memories/cat?path={first_file}")
            assert cat_resp.status_code == 200
            assert len(cat_resp.json()["content"]) > 0
