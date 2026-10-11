"""Red Team Pydantic schemas for running the HAZOP Red Team agent."""
from typing import Literal
from pydantic import BaseModel, Field


class RedTeamRunRequest(BaseModel):
    """Schema for POST /hazop-rows/{row_code}/red-team (and /stream)."""
    max_proposals: int = Field(
        default=2,
        ge=1,
        le=2,
        description="Maximum proposals to generate (1 or 2)"
    )
    focus: Literal["common_cause", "worsened", "any"] = Field(
        default="any",
        description="What kind of scenario the agent should look for"
    )
