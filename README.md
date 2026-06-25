# Memory Wiki

A service that ingests conversation transcripts, extracts structured memories via Claude, stores them as a navigable file tree in MinIO (S3-compatible), and exposes them through unix-style REST endpoints (`ls`, `cat`, `grep`).

## Quick Start

```bash
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

docker compose up --build
```

API is available at `http://localhost:8000`  
MinIO console at `http://localhost:9001` (user: `minioadmin`, pass: `minioadmin`)  
Interactive docs at `http://localhost:8000/docs`

---

## API Reference

### Transcripts

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/transcripts` | Ingest a transcript → enqueues memory extraction |
| `GET`  | `/transcripts/{id}` | Retrieve transcript and processing status |

**POST /transcripts**
```json
{ "content": "Alice is my manager at TechCorp. She prefers async comms." }
```
Returns: `{ "id": "...", "status": "pending", "job_id": "...", ... }`

Status values: `pending → processing → completed | failed`

### Memories (unix-style)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/memories/ls?path=/` | List directory entries |
| `GET` | `/memories/cat?path=/people/alice.md` | Read file content |
| `GET` | `/memories/grep?pattern=Python&path=/` | Search across files |

---

## Architecture

### Memory File Tree

Memories are stored in MinIO under a category-based tree:

```
memories/
├── people/          alice-smith.md, bob-jones.md
├── topics/          project-alpha.md, python.md
├── preferences/     communication-style.md
├── skills/          backend-engineering.md
└── events/          2024-01-15-sprint-review.md
```

Each file has YAML frontmatter (category, subject, tags, sources, timestamps) followed by structured markdown with H2 sections — designed to be grep-friendly.

**Example file: `/people/alice-smith.md`**
```markdown
---
category: people
subject: Alice Smith
slug: alice-smith
tags: [colleague, manager, engineering]
sources: [transcript-id-1, transcript-id-2]
created_at: 2024-01-15T10:00:00+00:00
updated_at: 2024-01-20T14:30:00+00:00
---

# Alice Smith

## Role
- Engineering Manager at TechCorp
- Based in San Francisco

## Working Style
- Prefers async communication over meetings
- Expert in distributed systems
```

### Background Processing

1. `POST /transcripts` saves the transcript to PostgreSQL and enqueues an ARQ job (Redis-backed).
2. The worker picks up the job, calls `extract_memories()` (Claude API), and writes each extracted memory to MinIO.
3. If an existing file matches the subject, Claude merges new information rather than overwriting (strategy: `create | append | update`).
4. The job has `max_tries=3` with exponential backoff. Status is tracked in the `transcripts` table.

### Memory Update Logic

When a new transcript references an existing subject:
- Claude receives the existing file content + new extracted facts
- Claude decides the merge strategy and produces the updated file
- Frontmatter (`sources`, `updated_at`) is patched deterministically without an LLM call

### Components

| Component | Technology |
|-----------|-----------|
| API | FastAPI + Uvicorn |
| Database | PostgreSQL (SQLAlchemy async) |
| Object storage | MinIO (S3-compatible via boto3) |
| Background jobs | ARQ (async Redis queue) |
| LLM | Anthropic Claude (`claude-sonnet-4-6`) |
| Orchestration | Docker Compose |

---

## Running Tests

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Unit + integration (no running services needed)
pytest tests/unit tests/integration -v

# End-to-end (requires docker compose up)
E2E=1 pytest tests/e2e/ -v
```

---

## Assumptions & Trade-offs

**Memory schema is category-scoped, not user-scoped.** This service stores memories for a single user/context. Multi-tenancy would require path prefixing by user ID.

**Synchronous MinIO client (boto3).** The worker is already in a thread-safe async context via ARQ. A truly async S3 client (aiobotocore) would improve throughput under high concurrency but adds complexity.

**LLM merge on every update.** Calling Claude to merge existing + new content is the highest-quality approach but costs tokens. An alternative: append-only with periodic compaction jobs.

**SQLite for tests.** Unit and integration tests use an in-memory SQLite DB (via aiosqlite) for speed. The production path uses PostgreSQL. Schema is kept compatible with both.

**No semantic search / embeddings.** `grep` is regex-based. Adding vector embeddings (pgvector or Pinecone) would enable semantic retrieval — the most impactful next step.

---

## What I'd Add With More Time

- **Semantic search**: embed memory files and expose `/memories/search?q=natural+language`
- **Alembic migrations**: replace `create_all` with proper schema versioning
- **Multi-user support**: path-prefix memories per user, add auth middleware
- **Webhook / SSE**: let clients subscribe to memory events instead of polling transcript status
- **Compaction job**: periodic ARQ task to merge fragmented memory files and prune stale facts
- **Observability**: OpenTelemetry traces + Sentry for LLM call latency and error rates
