"""Chat service for the knowledge assistant.

Endpoints served:
    POST /chat-sessions                               - Open a chat session (201)
    GET  /chat-sessions/{session_id}/messages         - Session history with citations
    POST /chat-sessions/{session_id}/messages         - Ask, wait for the full answer
    POST /chat-sessions/{session_id}/messages/stream  - Ask, stream the answer (SSE)

Writes (one transaction per answer): chat_messages, citations, agent_runs, audit_log
"""
import asyncio
import logging
from datetime import timedelta
from typing import AsyncIterator, Awaitable, Callable, Optional
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from config.databases.postgresql import AsyncSessionLocal
from config.settings import env
from app.agents.base import AgentEvent
from app.agents.knowledge.agent import KnowledgeAgent
from app.agents.knowledge.prompts import KB_PROMPT_VERSION
from app.agents.knowledge.schemas import KnowledgeInput
from app.engines.guardrail import get_guardrail
from app.models.agent_run_model import AgentRun
from app.models.chat_message_model import ChatMessage
from app.models.chat_session_model import ChatSession
from app.models.citation_model import Citation
from app.models.columns import utcnow
from app.models.enums import AgentName, CitationTarget, UserRole
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.chat_message_repository import ChatMessageRepository
from app.repositories.chat_session_repository import ChatSessionRepository
from app.repositories.prompt_template_repository import PromptTemplateRepository
from app.schemas.auth_schema import CurrentUser
from app.services.audit_records import audit_entry, audit_id
from app.services.retrieval_index import retrieval_index
from app.utils.ids import is_uuid, new_id
from app.utils.response import response_error, response_success
from app.utils.sse import SSE_HEADERS, FrameCounter, generate_run_id

logger = logging.getLogger(__name__)
HISTORY_MESSAGES = 12   # last 6 turns
READ_ANY_SESSION = (UserRole.AUDITOR, UserRole.ADMIN)

PersistFn = Callable[[dict, dict], Awaitable[dict]]


def guardrail():
    return get_guardrail(str(env.demo_data_path / "seed" / "guardrail_rules.yaml"))


async def run_knowledge(
    payload: KnowledgeInput,
    persist: Optional[PersistFn],
    message_id: Optional[str] = None,
) -> AsyncIterator[AgentEvent]:
    """Run the knowledge agent with this process's dependencies (chat endpoints and evaluation)."""
    await retrieval_index.ensure_loaded()
    deps = {
        "index": retrieval_index,
        "guardrail": guardrail(),
        "persist": persist,
        "llm_enabled": env.llm_enabled,
    }
    async for event in KnowledgeAgent().stream(payload, generate_run_id(), message_id or new_id(), deps):
        yield event


class ChatService:
    """
    Service for chat sessions and cited answers.

    REQUEST-SCOPED: Created per request with injected session.
    Pre-stream checks: session exists (404), session belongs to the caller (403).
    """

    def __init__(self, db: AsyncSession):
        """Initialize ChatService with a DB session."""
        self.db = db
        self.sessions = ChatSessionRepository(db)

    async def create_session(self, user: CurrentUser) -> JSONResponse:
        """Create a session; its id is also the LangGraph thread_id."""
        session = await self.sessions.create(ChatSession(user_id=user.id))
        return response_success({"session_id": session.id, "created_at": session.started_at}, msg="Created", code=201)

    async def get_messages(self, session_id: str, user: CurrentUser) -> JSONResponse:
        """Return the thread oldest first; assistant messages in CitedAnswer shape."""
        session = await self.sessions.get_by_id(session_id) if is_uuid(session_id) else None
        if not session:
            return response_error(f"Chat session {session_id} not found", code=404)
        if session.user_id != user.id and user.role not in READ_ANY_SESSION:
            return response_error("This chat session belongs to another user", code=403)

        messages = await ChatMessageRepository(self.db).list_by_session(session.id)
        runs = await AgentRunRepository(self.db).list_by_chat_messages([m.id for m in messages if m.role == "assistant"])
        outputs = {run.chat_message_id: run.output for run in runs if isinstance(run.output, dict)}
        thread = []
        for message in messages:
            if message.role == "user":
                thread.append({"message_id": message.id, "role": "user", "content": message.content,
                               "created_at": message.created_at})
            else:
                answer = outputs.get(message.id) or {
                    "message_id": message.id, "kind": message.kind, "confidence": message.confidence,
                    "content": message.content, "steps": [], "citations": [],
                }
                thread.append({**answer, "role": "assistant", "created_at": message.created_at})
        return response_success(thread, metadata={"session_id": session.id, "total": len(thread)})

    async def send_message(
        self,
        session_id: str,
        content: str,
        asset_tag: Optional[str],
        user: CurrentUser
    ) -> JSONResponse:
        """Run the knowledge graph to completion and return the CitedAnswer."""
        session = await self._own_session(session_id, user)
        payload = await self._payload(session, content, asset_tag, user)
        persist = self._persist_fn(session.id, payload, utcnow())
        result, error = None, None
        async for event in run_knowledge(payload, persist):
            if event.type == "RUN_FINISHED":
                result = event.data.get("result")
            elif event.type == "RUN_ERROR":
                error = event.data
        if error:
            await _save_failure(session.id, payload, error.get("code", "LLM_UNAVAILABLE"))
            if error.get("code") == "LLM_RATE_LIMITED":
                return response_error(error["message"], code=429)
            return response_error("AI service unavailable, please retry", code=500)
        return response_success(result, msg="Created", code=201)

    async def stream_message(
        self,
        session_id: str,
        content: str,
        asset_tag: Optional[str],
        user: CurrentUser
    ) -> StreamingResponse:
        """Stream the knowledge graph as AG-UI events; RUN_FINISHED carries the CitedAnswer."""
        session = await self._own_session(session_id, user)
        payload = await self._payload(session, content, asset_tag, user)
        return StreamingResponse(
            self._frames(session.id, payload),
            media_type="text/event-stream",
            headers=SSE_HEADERS,
        )

    # ------------------------------------------------------------------ helpers
    async def _own_session(self, session_id: str, user: CurrentUser) -> ChatSession:
        session = await self.sessions.get_by_id(session_id) if is_uuid(session_id) else None
        if not session:
            response_error(f"Chat session {session_id} not found", code=404)
        if session.user_id != user.id:
            response_error("This chat session belongs to another user", code=403)
        return session

    async def _payload(self, session: ChatSession, content: str, asset_tag: Optional[str], user: CurrentUser) -> KnowledgeInput:
        history = await ChatMessageRepository(self.db).list_last(session.id, HISTORY_MESSAGES)
        return KnowledgeInput(
            question=content.strip(),
            asset_tag=asset_tag or None,
            user_id=user.id,
            session_id=session.id,
            history=[(m.role, m.content) for m in history if m.kind not in ("cancelled",)],
        )

    def _persist_fn(self, session_id: str, payload: KnowledgeInput, asked_at) -> PersistFn:
        async def persist(state: dict, answer: dict) -> dict:
            return await _save_answer(session_id, payload, asked_at, state, answer)
        return persist

    async def _frames(self, session_id: str, payload: KnowledgeInput) -> AsyncIterator[str]:
        frames = FrameCounter()
        asked_at = utcnow()
        persisted = False
        partial: list[str] = []
        message_id = new_id()

        async def persist(state: dict, answer: dict) -> dict:
            nonlocal persisted
            saved = await _save_answer(session_id, payload, asked_at, state, answer)
            persisted = True
            return saved

        try:
            async for event in run_knowledge(payload, persist, message_id):
                if event.type == "TEXT_MESSAGE_CONTENT":
                    partial.append(event.data.get("delta", ""))
                if event.type == "RUN_ERROR":
                    await _save_failure(session_id, payload, event.data.get("code", "LLM_UNAVAILABLE"))
                yield frames.frame(event.type, **event.data)
        except (asyncio.CancelledError, GeneratorExit):
            # Client went away: keep what was streamed, marked cancelled (spec Section 5).
            if not persisted:
                await asyncio.shield(_save_cancelled(session_id, payload, asked_at, message_id, "".join(partial)))
            raise


async def _prompt_template_id(db: AsyncSession) -> Optional[str]:
    template = await PromptTemplateRepository(db).get_by_version(AgentName.KNOWLEDGE_AGENT, KB_PROMPT_VERSION)
    return template.id if template else None


async def _save_answer(session_id: str, payload: KnowledgeInput, asked_at, state: dict, answer: dict) -> dict:
    """chat_messages + citations + agent_runs + audit_log in one transaction (operation 4)."""
    kind = answer["kind"]
    usage = state.get("usage") or {}
    question = payload.question
    async with AsyncSessionLocal() as db:
        db.add(ChatMessage(session_id=session_id, role="user", content=question, created_at=asked_at))
        assistant = ChatMessage(
            id=answer["message_id"], session_id=session_id, role="assistant", content=answer["content"],
            kind=kind, confidence=answer.get("confidence"),
            guardrail_reason=(answer.get("guardrail") or {}).get("rule_id"),
            created_at=max(utcnow(), asked_at + timedelta(milliseconds=1)),
        )
        db.add(assistant)
        await db.flush()
        db.add_all(
            Citation(
                target_type=CitationTarget.CHUNK, chunk_id=c["chunk_id"], chat_message_id=assistant.id,
                resolved=c.get("resolved", True), raw_ref=f"[{c['index']}] doc:{c['doc_code']}#{c.get('section') or ''}",
            )
            for c in answer.get("citations", [])
        )
        model_called = kind == "answer" or bool(usage)
        run = AgentRun(
            agent=AgentName.GUARDRAIL if kind == "refused" else AgentName.KNOWLEDGE_AGENT,
            prompt_template_id=await _prompt_template_id(db) if model_called else None,
            model_id=answer.get("model_id") if model_called else None,
            model_endpoint="cloud_api" if model_called else None,
            input={
                "question": question, "asset_tag": payload.asset_tag, "session_id": session_id,
                "hits": [{"chunk_id": h["chunk_id"], "doc_code": h["doc_code"], "score": h["score"]} for h in state.get("hits") or []],
            },
            output=answer,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            latency_ms=answer.get("latency_ms"),
            chat_message_id=assistant.id,
        )
        db.add(run)
        short = question if len(question) <= 80 else question[:77] + "…"
        if kind == "refused":
            rule = answer["guardrail"]["rule_id"]
            audit = audit_entry(
                "guardrail_refusal", "chat_messages", assistant.id, text=f'Refused ({rule}): "{short}"',
                outcome="refused", actor_agent=AgentName.GUARDRAIL, rule_id=rule, model_calls=0, session_id=session_id,
            )
        elif kind == "insufficient":
            audit = audit_entry(
                "insufficient", "chat_messages", assistant.id, text=f'Insufficient evidence: "{short}"',
                outcome="logged", actor_agent=AgentName.KNOWLEDGE_AGENT, prompt_version=KB_PROMPT_VERSION,
                model_id=answer.get("model_id"), model_calls=1 if usage else 0, session_id=session_id,
                sources=len(state.get("hits") or []),
            )
        else:
            audit = audit_entry(
                "answer", "chat_messages", assistant.id, text=f'Answered "{short}"', outcome="answered",
                sources=len(answer.get("citations", [])), actor_agent=AgentName.KNOWLEDGE_AGENT,
                model_id=answer.get("model_id"), prompt_version=KB_PROMPT_VERSION,
                confidence=answer.get("confidence"), model_calls=1, session_id=session_id,
            )
        db.add(audit)
        await db.flush()
        run.output = {**answer, "audit_id": audit_id(audit.id)}
        await db.commit()
    return {"audit_id": audit_id(audit.id)}


async def _save_cancelled(session_id: str, payload: KnowledgeInput, asked_at, message_id: str, partial: str) -> None:
    try:
        async with AsyncSessionLocal() as db:
            db.add(ChatMessage(session_id=session_id, role="user", content=payload.question, created_at=asked_at))
            db.add(ChatMessage(id=message_id, session_id=session_id, role="assistant",
                               content=partial or "(cancelled before any text)", kind="cancelled",
                               created_at=max(utcnow(), asked_at + timedelta(milliseconds=1))))
            await db.flush()
            db.add(audit_entry(
                "answer_cancelled", "chat_messages", message_id, text="Answer cancelled: the client disconnected",
                outcome="logged", actor_agent=AgentName.KNOWLEDGE_AGENT, session_id=session_id,
            ))
            await db.commit()
    except Exception:
        logger.exception("Could not save cancelled answer for session %s", session_id)


async def _save_failure(session_id: str, payload: KnowledgeInput, code: str) -> None:
    """Keep the question and an audit record when the model call failed."""
    try:
        async with AsyncSessionLocal() as db:
            message = ChatMessage(session_id=session_id, role="user", content=payload.question)
            db.add(message)
            await db.flush()
            db.add(audit_entry(
                "answer_failed", "chat_messages", message.id, text=f"Answer failed: {code}",
                outcome="logged", actor_agent=AgentName.KNOWLEDGE_AGENT, code=code, session_id=session_id,
            ))
            await db.commit()
    except Exception:
        logger.exception("Could not save failed answer for session %s", session_id)
