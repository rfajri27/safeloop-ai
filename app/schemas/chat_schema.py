"""Chat Pydantic schemas for the knowledge assistant."""
from typing import Optional
from pydantic import BaseModel, Field


class ChatMessageCreate(BaseModel):
    """Schema for POST /chat-sessions/{session_id}/messages (and /stream)."""
    content: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User question"
    )
    asset_tag: Optional[str] = Field(
        None,
        max_length=32,
        description="Optional asset tag that narrows retrieval, e.g. P-101"
    )
