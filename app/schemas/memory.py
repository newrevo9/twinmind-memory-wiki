from typing import Literal

from pydantic import BaseModel


class MemoryEntry(BaseModel):
    name: str
    path: str
    type: Literal["file", "directory"]
    size: int | None = None
    last_modified: str | None = None


class LsResponse(BaseModel):
    path: str
    entries: list[MemoryEntry]


class CatResponse(BaseModel):
    path: str
    content: str
    last_modified: str | None = None


class GrepMatch(BaseModel):
    path: str
    line_number: int
    line: str


class GrepResponse(BaseModel):
    pattern: str
    search_path: str
    matches: list[GrepMatch]
