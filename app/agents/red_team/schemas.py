"""Red Team structured output schemas (spec Section 7.3)."""
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from app.models.enums import GuideWord, HazopParam

TITLE_MAX = 120


class RedTeamInput(BaseModel):
    row_code: str
    max_proposals: int = Field(default=2, ge=1, le=2)
    focus: Literal["common_cause", "worsened", "any"] = "any"


class HazopProposalDraft(BaseModel):
    kind: Literal["new_scenario", "worsened"]
    title: str = Field(max_length=TITLE_MAX)
    guide_word: GuideWord
    parameter: HazopParam
    deviation: str
    cause: str
    consequence: str
    severity: int = Field(ge=1, le=5)
    likelihood: int = Field(ge=1, le=5)
    entities: list[str] = Field(description="Every equipment or instrument tag named")
    safeguards: list[str] = Field(description="Safeguard ref codes")
    recommendation: str = Field(description="A check, test or review; never a control action")
    citations: list[str] = Field(description='"doc:SOP-P101-02#step-3" or "asset_model:L-104"')

    @field_validator("title", mode="before")
    @classmethod
    def clip_title(cls, value):
        return value[:TITLE_MAX] if isinstance(value, str) else value


class RedTeamOutput(BaseModel):
    proposals: list[HazopProposalDraft] = Field(max_length=2)
