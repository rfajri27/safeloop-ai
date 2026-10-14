"""Knowledge agent: runs the graph and yields AG-UI AgentEvents (spec Section 5, chat stream)."""
import logging
import time
from typing import Any, AsyncIterator, Optional
from app.agents.base import AgentEvent, LLMError
from app.agents.knowledge.graph import build_knowledge_graph
from app.agents.knowledge.schemas import KnowledgeInput

logger = logging.getLogger(__name__)


class KnowledgeAgent:
    """Stateless wrapper around the compiled graph."""

    def __init__(self):
        self.graph = build_knowledge_graph()

    async def stream(
        self,
        payload: KnowledgeInput,
        run_id: str,
        message_id: str,
        deps: dict[str, Any],
    ) -> AsyncIterator[AgentEvent]:
        """RUN_STARTED, node events, then RUN_FINISHED with the CitedAnswer (or RUN_ERROR)."""
        yield AgentEvent("RUN_STARTED", {
            "runId": run_id,
            "threadId": payload.session_id,
            "input": {"content": payload.question, "asset_tag": payload.asset_tag},
        })
        state = {
            "run_id": run_id,
            "message_id": message_id,
            "question": payload.question,
            "asset_tag": payload.asset_tag,
            "user_id": payload.user_id,
            "history": payload.history,
        }
        config = {
            "configurable": {"started": time.perf_counter(), **deps},
            "run_name": "knowledge_agent",
            "metadata": {"prompt_version": "kb.v1", "user_id": payload.user_id},
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
            logger.exception("Knowledge run %s failed", run_id)
            yield AgentEvent("RUN_ERROR", {"runId": run_id, "message": "The answer could not be completed", "code": "INTERNAL_ERROR"})
            return
        yield AgentEvent("RUN_FINISHED", {"runId": run_id, "result": (final or {}).get("answer")})
