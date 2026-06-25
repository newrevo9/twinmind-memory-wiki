from fastapi import APIRouter, HTTPException, Query

from app.schemas.memory import CatResponse, GrepMatch, GrepResponse, LsResponse, MemoryEntry
from app.services.storage import get_object, grep_objects, list_objects

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("/ls", response_model=LsResponse, summary="List memory directory (unix ls)")
async def ls(path: str = Query(default="/", description="Directory path to list")):
    try:
        raw = list_objects(path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return LsResponse(path=path, entries=[MemoryEntry(**e) for e in raw])


@router.get("/cat", response_model=CatResponse, summary="Read memory file (unix cat)")
async def cat(path: str = Query(..., description="File path to read (must end in .md)")):
    if not path.endswith(".md"):
        raise HTTPException(status_code=400, detail="Path must point to a .md file")
    content = get_object(path)
    if content is None:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    return CatResponse(path=path, content=content)


@router.get("/grep", response_model=GrepResponse, summary="Search memory files (unix grep)")
async def grep(
    pattern: str = Query(..., description="Regex or literal string to search for"),
    path: str = Query(default="/", description="Directory to search in (recursive)"),
):
    if not pattern.strip():
        raise HTTPException(status_code=422, detail="Pattern cannot be empty")
    try:
        raw = grep_objects(pattern, path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return GrepResponse(
        pattern=pattern,
        search_path=path,
        matches=[GrepMatch(**m) for m in raw],
    )
