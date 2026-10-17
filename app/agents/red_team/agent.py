"""Red Team agent: runs the graph and yields AG-UI AgentEvents (spec Section 6.6)."""
import logging
from typing import Any, AsyncIterator, Optional
from app.agents.base import AgentEvent, LLMError
from app.agents.red_team.graph import build_red_team_graph
from app.agents.red_team.schemas import RedTeamInput

logger = logging.getLogger(__name__)


class RedTeamAgent:
    """Stateless wrapper around the compiled graph."""

    def __init__(self):
        self.graph = build_red_team_graph()

    async def stream(self, payload: RedTeamInput, run_id: str, deps: dict[str, Any]) -> AsyncIterator[AgentEvent]:
        """RUN_STARTED, node events, then RUN_FINISHED with the run result (or RUN_ERROR)."""
        yield AgentEvent("RUN_STARTED", {"runId": run_id, "threadId": None, "input": payload.model_dump()})
        state = {"run_id": run_id, **payload.model_dump()}
        config = {
            "configurable": deps,
            "run_name": "red_team",
            "metadata": {"prompt_version": "redteam.v1", "row_code": payload.row_code},
        }
        final: Optional[dict] = None
        try:
            async for mode, chunk in self.graph.astream(state, config, stream_mode=["custom", "values"]):
                if mode == "custom":
                    data = dict(chunk)
                    yield AgentEvent(data.pop("type"), data)
                else:
                    final = chunk
        except LLMError as exc:
            yield AgentEvent("RUN_ERROR", {"runId": run_id, "message": exc.message, "code": exc.code})
            return
        except Exception:
            logger.exception("Red Team run %s failed", run_id)
            yield AgentEvent("RUN_ERROR", {"runId": run_id, "message": "The Red Team run could not be completed", "code": "INTERNAL_ERROR"})
            return
        yield AgentEvent("RUN_FINISHED", {"runId": run_id, "result": (final or {}).get("result")})
