"""Evaluation Pydantic schemas for starting evaluation runs."""
from typing import Literal
from pydantic import BaseModel, Field


GoldenSet = Literal["hazop_rows", "qa", "out_of_corpus", "guardrail", "rca"]


class EvalRunCreate(BaseModel):
    """Schema for POST /eval-runs."""
    freeze: bool = Field(
        default=False,
        description="Mark this run as the frozen demo-day run"
    )
    sets: list[GoldenSet] = Field(
        default=["hazop_rows", "qa", "out_of_corpus", "guardrail"],
        min_length=1,
        description="Golden sets to evaluate"
    )
