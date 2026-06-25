import json
import logging
from typing import Literal

import anthropic
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {"people", "topics", "preferences", "skills", "events"}

EXTRACTION_SYSTEM_PROMPT = """You are a memory extraction system for a personal AI assistant called TwinMind.
Your job is to extract discrete, durable memories from conversation transcripts and organize them into a structured file tree.

Memory categories:
- people: Named individuals (colleagues, friends, contacts) — include role, relationship, key traits
- topics: Subject areas and projects discussed — include context, key facts, decisions
- preferences: User preferences, habits, recurring choices
- skills: User's skills, expertise, domain knowledge
- events: Specific dated events, meetings, milestones (prefix slug with ISO date, e.g. 2024-01-15-)

For each memory, write structured markdown content with clear H2 sections so it stays grep-friendly.

Return ONLY valid JSON in this exact shape:
{
  "memories": [
    {
      "category": "people|topics|preferences|skills|events",
      "subject": "Human readable name",
      "slug": "url-safe-slug",
      "content": "# Subject\\n\\n## Section\\n- fact",
      "tags": ["tag1", "tag2"],
      "merge_strategy": "create|append|update"
    }
  ],
  "summary": "One sentence summary of the transcript"
}

merge_strategy rules:
- create: brand new subject, no existing file
- append: add new facts to existing subject
- update: correct or replace outdated information

Extract only factual, durable information. Skip small talk and transient context.
Write content that remains useful months later when retrieved by grep."""

MERGE_SYSTEM_PROMPT = """You are merging new information into an existing memory file.
Preserve the frontmatter (between --- markers) exactly as-is.
Integrate new facts naturally into the existing sections, or add new sections.
Remove duplicates. Keep content concise and grep-friendly.
Return only the merged file content, no explanation."""


async def extract_memories(
    transcript_content: str,
    existing_paths: list[str] | None = None,
) -> "ExtractionResult":
    context = ""
    if existing_paths:
        context = f"\nExisting memory paths (use append/update for matching subjects):\n" + "\n".join(existing_paths)

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Extract memories from this transcript:{context}\n\n<transcript>\n{transcript_content}\n</transcript>",
            }
        ],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if present
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    data = json.loads(raw)
    return ExtractionResult(**data)


async def merge_memory_content(existing_content: str, new_content: str, merge_strategy: str) -> str:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2048,
        system=MERGE_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Strategy: {merge_strategy}\n\n"
                    f"<existing>\n{existing_content}\n</existing>\n\n"
                    f"<new>\n{new_content}\n</new>"
                ),
            }
        ],
    )
    return response.content[0].text.strip()


class ExtractedMemory(BaseModel):
    category: str
    subject: str
    slug: str
    content: str
    tags: list[str]
    merge_strategy: Literal["create", "append", "update"]


class ExtractionResult(BaseModel):
    memories: list[ExtractedMemory]
    summary: str
