import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.llm import ExtractionResult, ExtractedMemory, extract_memories


def _mock_response(payload: dict) -> MagicMock:
    msg = MagicMock()
    msg.content = [MagicMock(text=json.dumps(payload))]
    return msg


def _mock_response_fenced(payload: dict) -> MagicMock:
    msg = MagicMock()
    msg.content = [MagicMock(text=f"```json\n{json.dumps(payload)}\n```")]
    return msg


SAMPLE_PAYLOAD = {
    "memories": [
        {
            "category": "people",
            "subject": "Alice Smith",
            "slug": "alice-smith",
            "content": "# Alice Smith\n\n## Role\n- Engineering Manager at TechCorp",
            "tags": ["colleague", "manager"],
            "merge_strategy": "create",
        }
    ],
    "summary": "Alice is the EM.",
}


@pytest.mark.asyncio
async def test_extract_returns_structured_result():
    with patch("app.services.llm.anthropic.AsyncAnthropic") as MockCls:
        MockCls.return_value.messages.create = AsyncMock(return_value=_mock_response(SAMPLE_PAYLOAD))
        result = await extract_memories("Alice is my manager at TechCorp.")

    assert isinstance(result, ExtractionResult)
    assert len(result.memories) == 1
    mem = result.memories[0]
    assert mem.subject == "Alice Smith"
    assert mem.category == "people"
    assert mem.merge_strategy == "create"


@pytest.mark.asyncio
async def test_extract_strips_json_code_fence():
    with patch("app.services.llm.anthropic.AsyncAnthropic") as MockCls:
        MockCls.return_value.messages.create = AsyncMock(
            return_value=_mock_response_fenced({"memories": [], "summary": "nothing"})
        )
        result = await extract_memories("Hello.")

    assert result.memories == []
    assert result.summary == "nothing"


@pytest.mark.asyncio
async def test_extract_passes_existing_paths():
    captured = {}

    async def fake_create(**kwargs):
        captured["messages"] = kwargs["messages"]
        return _mock_response({"memories": [], "summary": "x"})

    with patch("app.services.llm.anthropic.AsyncAnthropic") as MockCls:
        MockCls.return_value.messages.create = fake_create
        await extract_memories("Hello.", existing_paths=["/people/bob.md"])

    assert "/people/bob.md" in captured["messages"][0]["content"]


@pytest.mark.asyncio
async def test_extract_invalid_json_raises():
    msg = MagicMock()
    msg.content = [MagicMock(text="not json at all")]

    with patch("app.services.llm.anthropic.AsyncAnthropic") as MockCls:
        MockCls.return_value.messages.create = AsyncMock(return_value=msg)
        with pytest.raises(Exception):
            await extract_memories("test")
