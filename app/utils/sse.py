"""SSE streaming helpers following AG-UI Protocol.

AG-UI (Agent-User Interaction) Protocol is an open, event-based standard
for real-time AI agent streaming. This module implements the core event types.

Reference: https://ag-ui.com/concepts/events

Event Categories:
- Lifecycle: RunStarted, RunFinished, RunError, StepStarted, StepFinished
- Text Message: TextMessageStart, TextMessageContent, TextMessageEnd
- Tool Call: ToolCallStart, ToolCallArgs, ToolCallEnd, ToolCallResult

Usage:
    from app.utils.sse import (
        sse_run_started, sse_step_started, sse_text_message_content,
        sse_tool_call_start, sse_run_finished, generate_run_id
    )
    
    async def stream():
        run_id = generate_run_id()
        yield sse_run_started(run_id, thread_id)
        yield sse_step_started("retrieve_books")
        # ... stream tokens ...
        yield sse_run_finished(run_id, result)
"""
import json
import time
import uuid
from enum import Enum
from typing import Any, Optional


class SSEEventType(str, Enum):
    """AG-UI Protocol event types."""
    # Lifecycle events
    RUN_STARTED = "RUN_STARTED"
    RUN_FINISHED = "RUN_FINISHED"
    RUN_ERROR = "RUN_ERROR"
    STEP_STARTED = "STEP_STARTED"
    STEP_FINISHED = "STEP_FINISHED"
    
    # Text message events
    TEXT_MESSAGE_START = "TEXT_MESSAGE_START"
    TEXT_MESSAGE_CONTENT = "TEXT_MESSAGE_CONTENT"
    TEXT_MESSAGE_END = "TEXT_MESSAGE_END"
    
    # Tool call events
    TOOL_CALL_START = "TOOL_CALL_START"
    TOOL_CALL_ARGS = "TOOL_CALL_ARGS"
    TOOL_CALL_END = "TOOL_CALL_END"
    TOOL_CALL_RESULT = "TOOL_CALL_RESULT"


def _timestamp_ms() -> int:
    """Get current timestamp in milliseconds."""
    return int(time.time() * 1000)


def _format_sse(event_type: str, event_data: dict) -> str:
    """Format event as SSE string following AG-UI Protocol.
    
    AG-UI Format (flat structure):
        data: {"type":"EVENT_TYPE", "timestamp":..., "field1":..., "field2":...}
        
        (blank line to end event)
    
    All event-specific fields are flat at root level, not nested under 'data'.
    """
    # Build flat payload: type + timestamp + all event fields at root
    payload = {
        "type": event_type,
        "timestamp": _timestamp_ms(),
        **event_data
    }
    
    return f"data: {json.dumps(payload)}\n\n"


# =============================================================================
# LIFECYCLE EVENTS
# =============================================================================

def sse_run_started(
    run_id: str,
    thread_id: str = None,
    input_data: Any = None
) -> str:
    """Emit when agent run begins.
    
    Args:
        run_id: Unique identifier for this run
        thread_id: Optional conversation thread ID
        input_data: Optional input that triggered the run
    """
    return _format_sse(
        SSEEventType.RUN_STARTED.value,
        {
            "runId": run_id,
            "threadId": thread_id,
            "input": input_data or {}
        }
    )


def sse_run_finished(run_id: str, result: Any = None) -> str:
    """Emit when agent run completes successfully.
    
    Args:
        run_id: Run identifier from sse_run_started
        result: Final result of the run
    """
    return _format_sse(
        SSEEventType.RUN_FINISHED.value,
        {"runId": run_id, "result": result}
    )


def sse_run_error(run_id: str, message: str, code: str = None) -> str:
    """Emit when agent run fails.
    
    Args:
        run_id: Run identifier
        message: Error message
        code: Optional error code
    """
    return _format_sse(
        SSEEventType.RUN_ERROR.value,
        {"runId": run_id, "message": message, "code": code}
    )


def sse_step_started(step_name: str, run_id: str = None) -> str:
    """Emit when entering a graph node/step.
    
    Args:
        step_name: Name of the step (e.g., "retrieve_books", "agent")
        run_id: Optional run identifier
    
    Example frontend display: "Searching books..."
    """
    return _format_sse(
        SSEEventType.STEP_STARTED.value,
        {"stepName": step_name, "runId": run_id}
    )


def sse_step_finished(step_name: str, run_id: str = None) -> str:
    """Emit when exiting a graph node/step.
    
    Args:
        step_name: Name of the completed step
        run_id: Optional run identifier
    """
    return _format_sse(
        SSEEventType.STEP_FINISHED.value,
        {"stepName": step_name, "runId": run_id}
    )


# =============================================================================
# TEXT MESSAGE EVENTS
# =============================================================================

def sse_text_message_start(message_id: str, role: str = "assistant") -> str:
    """Emit when starting to stream a text message.
    
    Args:
        message_id: Unique message identifier
        role: Message role (assistant, user, system)
    """
    return _format_sse(
        SSEEventType.TEXT_MESSAGE_START.value,
        {"messageId": message_id, "role": role}
    )


def sse_text_message_content(message_id: str, delta: str) -> str:
    """Emit for each text token/chunk.
    
    Args:
        message_id: Message identifier from sse_text_message_start
        delta: Text chunk to append
    
    Example: delta="Hello" -> delta=" world" -> delta="!"
    """
    return _format_sse(
        SSEEventType.TEXT_MESSAGE_CONTENT.value,
        {"messageId": message_id, "delta": delta}
    )


def sse_text_message_end(message_id: str) -> str:
    """Emit when text message is complete.
    
    Args:
        message_id: Message identifier
    """
    return _format_sse(
        SSEEventType.TEXT_MESSAGE_END.value,
        {"messageId": message_id}
    )


# =============================================================================
# TOOL CALL EVENTS
# =============================================================================

def sse_tool_call_start(
    tool_call_id: str,
    tool_call_name: str,
    parent_message_id: str = None
) -> str:
    """Emit when agent starts calling a tool.
    
    Args:
        tool_call_id: Unique tool call identifier
        tool_call_name: Name of the tool being called
        parent_message_id: ID of message that triggered this tool call
    
    Example frontend display: "Using search_web tool..."
    """
    return _format_sse(
        SSEEventType.TOOL_CALL_START.value,
        {
            "toolCallId": tool_call_id,
            "toolCallName": tool_call_name,
            "parentMessageId": parent_message_id
        }
    )


def sse_tool_call_args(tool_call_id: str, delta: str) -> str:
    """Emit tool call arguments (streamed incrementally).
    
    Args:
        tool_call_id: Tool call identifier
        delta: Argument chunk
    """
    return _format_sse(
        SSEEventType.TOOL_CALL_ARGS.value,
        {"toolCallId": tool_call_id, "delta": delta}
    )


def sse_tool_call_end(tool_call_id: str) -> str:
    """Emit when tool call arguments are complete.
    
    Args:
        tool_call_id: Tool call identifier
    """
    return _format_sse(
        SSEEventType.TOOL_CALL_END.value,
        {"toolCallId": tool_call_id}
    )


def sse_tool_call_result(
    tool_call_id: str,
    content: Any,
    message_id: str = None
) -> str:
    """Emit tool execution result.
    
    Args:
        tool_call_id: Tool call identifier
        content: Result from tool execution
        message_id: Optional message ID for this result
    """
    return _format_sse(
        SSEEventType.TOOL_CALL_RESULT.value,
        {
            "toolCallId": tool_call_id,
            "messageId": message_id or f"msg_{tool_call_id}",
            "content": content,
            "role": "tool"
        }
    )


# =============================================================================
# UTILITY
# =============================================================================

def sse_heartbeat() -> str:
    """Send heartbeat comment to keep connection alive.
    
    Heartbeats prevent proxy/load balancer timeouts on idle connections.
    Should be sent periodically (e.g., every 15-30 seconds).
    """
    return ": heartbeat\n\n"


def generate_run_id() -> str:
    """Generate unique run ID."""
    return f"run_{uuid.uuid4().hex[:12]}"


def generate_message_id() -> str:
    """Generate unique message ID."""
    return f"msg_{uuid.uuid4().hex[:12]}"


def generate_tool_call_id() -> str:
    """Generate unique tool call ID."""
    return f"call_{uuid.uuid4().hex[:12]}"
