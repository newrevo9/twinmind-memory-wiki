"""
Memory file tree layout:
  memories/
  ├── people/          {slug}.md  — named individuals
  ├── topics/          {slug}.md  — projects, concepts, technologies
  ├── preferences/     {slug}.md  — habits and personal choices
  ├── skills/          {slug}.md  — expertise and knowledge areas
  └── events/          {date}-{slug}.md  — dated occurrences

Each file has YAML frontmatter followed by structured markdown body.
New transcripts may create, append to, or update existing files via LLM merge.
"""

import logging
from datetime import datetime, timezone

from slugify import slugify

from app.services.llm import (
    VALID_CATEGORIES,
    ExtractedMemory,
    ExtractionResult,
    extract_memories,
    merge_memory_content,
)
from app.services.storage import get_object, list_objects, put_object

logger = logging.getLogger(__name__)


def _memory_path(category: str, slug: str) -> str:
    return f"{category}/{slug}.md"


def _build_frontmatter(memory: ExtractedMemory, transcript_id: str, now: str) -> str:
    tags = ", ".join(memory.tags)
    return (
        f"---\n"
        f"category: {memory.category}\n"
        f"subject: {memory.subject}\n"
        f"slug: {memory.slug}\n"
        f"tags: [{tags}]\n"
        f"sources: [{transcript_id}]\n"
        f"created_at: {now}\n"
        f"updated_at: {now}\n"
        f"---\n\n"
    )


def _patch_frontmatter(content: str, transcript_id: str) -> str:
    """Update sources list and updated_at in existing frontmatter without LLM call."""
    now = datetime.now(timezone.utc).isoformat()
    lines = content.splitlines()
    result = []
    in_front = False

    for i, line in enumerate(lines):
        if i == 0 and line.strip() == "---":
            in_front = True
            result.append(line)
            continue

        if in_front and line.strip() == "---":
            in_front = False
            result.append(line)
            continue

        if in_front:
            if line.startswith("sources:") and transcript_id not in line:
                existing = line[len("sources:"):].strip().strip("[]")
                line = f"sources: [{existing}, {transcript_id}]"
            elif line.startswith("updated_at:"):
                line = f"updated_at: {now}"

        result.append(line)

    return "\n".join(result)


async def process_transcript(transcript_id: str, content: str) -> list[str]:
    existing_paths = []
    for cat in VALID_CATEGORIES:
        for entry in list_objects(cat):
            if entry["type"] == "file":
                existing_paths.append(entry["path"])

    result: ExtractionResult = await extract_memories(content, existing_paths)
    written: list[str] = []

    for memory in result.memories:
        if memory.category not in VALID_CATEGORIES:
            logger.warning("Unknown category '%s' — skipping", memory.category)
            continue

        slug = memory.slug or slugify(memory.subject)
        path = _memory_path(memory.category, slug)
        now = datetime.now(timezone.utc).isoformat()

        try:
            existing = get_object(path)

            if existing is None:
                file_content = _build_frontmatter(memory, transcript_id, now) + memory.content
                put_object(path, file_content)
                logger.info("Created memory: %s", path)
            else:
                merged_body = await merge_memory_content(
                    existing_content=existing,
                    new_content=memory.content,
                    merge_strategy=memory.merge_strategy,
                )
                final = _patch_frontmatter(merged_body, transcript_id)
                put_object(path, final)
                logger.info("Updated memory (%s): %s", memory.merge_strategy, path)

            written.append(path)

        except Exception:
            logger.error("Failed to write memory %s", path, exc_info=True)
            raise

    return written
