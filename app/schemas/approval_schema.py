"""Approval Pydantic schemas for deciding approval items."""
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, model_validator


class ApprovalDecisionRequest(BaseModel):
    """Schema for POST /approval-items/{item_id}/decision."""
    decision: Literal["approved", "rejected"] = Field(
        ...,
        description="Reviewer decision"
    )
    reason: Optional[str] = Field(
        None,
        max_length=2000,
        description="Required (>= 5 characters) when rejecting"
    )
    edited_body: Optional[dict[str, Any]] = Field(
        None,
        description="Reviewer edits to the draft body"
    )

    @model_validator(mode="after")
    def check_reason(self):
        if self.decision == "rejected" and len((self.reason or "").strip()) < 5:
            raise ValueError("Reason is required to reject")
        return self
