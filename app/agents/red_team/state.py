"""Red Team graph state (spec Section 7.2)."""
from typing import Any, Literal, Optional, TypedDict
from app.engines.judge import JudgeContext


class RedTeamState(TypedDict, total=False):
    run_id: str
    row_code: str
    max_proposals: int                   # 1 or 2
    focus: Literal["common_cause", "worsened", "any"]
    context: dict[str, Any]              # row, linked assets + health, safeguards + dependencies, top chunks
    judge_context: JudgeContext
    raw: Optional[list[dict[str, Any]]]  # Gemini structured output, as dicts
    schema_valid: bool
    usage: dict[str, Any]                # model_id, input_tokens, output_tokens, latency_ms
    proposals: list[dict[str, Any]]      # drafts with index, proposed_row_code and verdict
    result: dict[str, Any]               # RUN_FINISHED.result
