"""Replay Pydantic schemas for starting and controlling scenario replays."""
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


ReplaySpeed = Literal[1, 3, 8]


class ReplayRunCreate(BaseModel):
    """Schema for POST /replay-runs."""
    scenario: Literal["S1", "S2"] = Field(..., description="Scenario code")
    speed: ReplaySpeed = Field(default=3, description="Replay speed: 1x, 3x or 8x")
    from_reset: bool = Field(
        default=True,
        description="Restore design-basis likelihoods before starting"
    )


class ReplayRunAction(BaseModel):
    """Schema for POST /replay-runs/{run_id}/actions."""
    action: Literal["pause", "resume", "reset", "set_speed"] = Field(
        ...,
        description="Replay control action"
    )
    speed: Optional[ReplaySpeed] = Field(
        None,
        description="New speed, required when action = set_speed"
    )

    @model_validator(mode="after")
    def check_speed(self):
        if self.action == "set_speed" and self.speed is None:
            raise ValueError("speed is required when action is set_speed")
        return self
