"""Base types shared by the LangGraph agents (team FastAPI AI standard, section 6).

Nodes report progress with LangGraph's stream writer as AG-UI shaped dicts
(`{"type": "STEP_STARTED", "stepName": ...}`); the agent wrapper turns the
custom stream into AgentEvents, and the service turns those into SSE frames.
Agents never open DB sessions: anything that touches the database (context
loading, persistence) is a callable the service passes in through the run
config, under `configurable`.
"""
import functools
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer


@dataclass
class AgentEvent:
    """One AG-UI event: `type` plus its fields."""
    type: str
    data: dict[str, Any] = field(default_factory=dict)

    def as_payload(self) -> dict[str, Any]:
        return {"type": self.type, **self.data}


class LLMError(Exception):
    """A model call failed after retries. `code` is LLM_UNAVAILABLE or LLM_RATE_LIMITED."""

    def __init__(self, code: str, message: str = "AI service unavailable, please retry"):
        super().__init__(message)
        self.code = code
        self.message = message


def classify_llm_error(exc: Exception) -> LLMError:
    """Map a provider exception to a RUN_ERROR code; provider text is never passed on."""
    text = f"{type(exc).__name__} {exc}".lower()
    if "429" in text or "resource_exhausted" in text or "quota" in text or ("rate" in text and "limit" in text):
        return LLMError("LLM_RATE_LIMITED", "AI service is rate limited, please try again shortly")
    return LLMError("LLM_UNAVAILABLE")


def emit(event_type: str, **fields: Any) -> None:
    """Write an AG-UI event to the custom stream (no-op outside a streaming run)."""
    try:
        writer = get_stream_writer()
    except Exception:
        return
    writer({"type": event_type, **fields})


def step(name: str):
    """Decorator: wrap a node in STEP_STARTED / STEP_FINISHED events."""
    def decorate(node: Callable[..., Awaitable[dict]]):
        @functools.wraps(node)
        async def wrapper(state: dict, config: RunnableConfig) -> dict:
            run_id = state.get("run_id")
            emit("STEP_STARTED", stepName=name, runId=run_id)
            result = await node(state, config)
            emit("STEP_FINISHED", stepName=name, runId=run_id)
            return result
        return wrapper
    return decorate


def configurable(config: Optional[RunnableConfig], key: str, default: Any = None) -> Any:
    """A dependency the service put in config["configurable"]."""
    return ((config or {}).get("configurable") or {}).get(key, default)


class Stopwatch:
    def __init__(self):
        self.started = time.perf_counter()

    @property
    def ms(self) -> int:
        return int((time.perf_counter() - self.started) * 1000)
