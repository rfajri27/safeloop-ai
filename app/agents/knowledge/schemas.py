"""Knowledge agent input and output schemas (spec Sections 6.7 and 7.3)."""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class KnowledgeInput(BaseModel):
    """What the service passes to the graph."""
    question: str = Field(..., min_length=1, max_length=2000)
    asset_tag: Optional[str] = None
    user_id: str
    session_id: Optional[str] = None
    history: list[tuple[str, str]] = Field(default_factory=list, description="(role, content), oldest first")


class AnswerCitation(BaseModel):
    index: int
    doc_code: str
    title: str
    chunk_id: str
    section: Optional[str] = None
    revision: Optional[str] = None
    is_synthetic: bool = True
    resolved: bool = True


class AnswerStep(BaseModel):
    text: str
    citations: list[int] = Field(default_factory=list)


class CitedAnswer(BaseModel):
    """RUN_FINISHED.result of the chat stream and the JSON twin's data."""
    message_id: str
    kind: Literal["answer", "insufficient", "refused", "cancelled"]
    confidence: Optional[Literal["high", "medium", "low"]] = None
    content: str
    steps: list[AnswerStep] = Field(default_factory=list)
    citations: list[AnswerCitation] = Field(default_factory=list)
    advisory_note: Optional[str] = None
    guardrail: Optional[dict] = None
    latency_ms: Optional[int] = None
    model_id: Optional[str] = None
    prompt_version: Optional[str] = None
    audit_id: Optional[str] = None
