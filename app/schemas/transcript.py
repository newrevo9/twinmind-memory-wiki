from datetime import datetime

from pydantic import BaseModel, field_validator


class TranscriptCreate(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Transcript content cannot be empty")
        return v


class TranscriptResponse(BaseModel):
    id: str
    content: str
    status: str
    job_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
