"""Audit service for the append-only audit log.

Endpoints served:
    GET /audit-events         - Append-only log, newest first, filterable
    GET /audit-events/summary - Counts for the header tiles

Reads: audit_log (no PUT, PATCH or DELETE exists)
"""
from typing import Optional
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_records import ACTOR_FILTERS, AUDIT_TYPES, audit_event_view, completeness_pct
from app.utils.ids import is_uuid
from app.utils.response import response_error, response_success


class AuditService:
    """
    Service for audit events.

    REQUEST-SCOPED: Created per request with injected session.
    """

    def __init__(self, db: AsyncSession):
        """Initialize AuditService with a DB session."""
        self.db = db
        self.repo = AuditLogRepository(db)

    async def get_events(
        self,
        event_type: Optional[str] = None,
        actor: Optional[str] = None,
        run_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> JSONResponse:
        """List audit events newest first; audit_id is `AUD-` + zero-padded id.

        `actor` takes the API value (health_agent, redteam, user, ...) or the
        label the Audit screen shows (Health Agent, Red Team, ...); any other
        value is matched against users' display names.
        """
        if run_id and not is_uuid(run_id):
            return response_error(f"Replay run {run_id} not found", code=404)
        filters = {"actions": AUDIT_TYPES[event_type.value] if event_type else None, "replay_run_id": run_id}
        if actor:
            key = actor.strip().lower()
            if key in ACTOR_FILTERS:
                agent = ACTOR_FILTERS[key]
                filters.update({"actor_agent": agent} if agent else {"any_user": True})
            else:
                users = [u for u in await UserRepository(self.db).list_filtered(limit=200) if u.display_name.lower() == key]
                if not users:
                    return response_success([], metadata={"total": 0, "skip": skip, "limit": limit})
                filters["actor_user"] = users[0].id

        events = await self.repo.list_filtered(**filters, skip=skip, limit=limit)
        total = await self.repo.count_filtered(**filters)
        names = await self._user_names({e.actor_user for e in events if e.actor_user})
        return response_success(
            [audit_event_view(event, names) for event in events],
            metadata={"total": total, "skip": skip, "limit": limit},
        )

    async def get_summary(self, run_id: Optional[str] = None) -> JSONResponse:
        """Return {complete_records_pct, events, blocked_by_judge, refused}."""
        if run_id and not is_uuid(run_id):
            return response_error(f"Replay run {run_id} not found", code=404)
        counts = await self.repo.count_by_action(run_id)
        events = await self.repo.list_filtered(replay_run_id=run_id, limit=100_000)
        return response_success({
            "complete_records_pct": completeness_pct(events),
            "events": sum(counts.values()),
            "blocked_by_judge": counts.get("judge_block", 0),
            "refused": counts.get("guardrail_refusal", 0),
            "by_type": {kind: sum(counts.get(a, 0) for a in actions) for kind, actions in AUDIT_TYPES.items()},
            "run_id": run_id,
        })

    async def _user_names(self, user_ids: set[str]) -> dict[str, str]:
        users = UserRepository(self.db)
        names = {}
        for user_id in user_ids:
            user = await users.get_by_id(user_id)
            names[user_id] = user.display_name if user else "Unknown user"
        return names
