"""Repository for AuditLog entity (append-only)."""
from typing import Optional, Sequence
from sqlalchemy import func, select
from app.repositories.base import AppendOnlyRepository
from app.models.audit_log_model import AuditLog
from app.models.enums import AgentName


class AuditLogRepository(AppendOnlyRepository[AuditLog]):
    """Repository for AuditLog queries.

    Write with add() inside the same transaction as the action it records,
    so an action without its audit record cannot commit (PO-5).
    """
    model_class = AuditLog

    def _filtered(
        self,
        query,
        actions: Optional[Sequence[str]],
        actor_agent: Optional[AgentName],
        actor_user: Optional[str],
        replay_run_id: Optional[str]
    ):
        if actions:
            query = query.where(AuditLog.action.in_(actions))
        if actor_agent:
            query = query.where(AuditLog.actor_agent == actor_agent)
        if actor_user:
            query = query.where(AuditLog.actor_user == actor_user)
        if replay_run_id:
            query = query.where(AuditLog.replay_run_id == replay_run_id)
        return query

    async def list_filtered(
        self,
        actions: Optional[Sequence[str]] = None,
        actor_agent: Optional[AgentName] = None,
        actor_user: Optional[str] = None,
        replay_run_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> Sequence[AuditLog]:
        """Audit events, newest first."""
        query = self._filtered(select(AuditLog), actions, actor_agent, actor_user, replay_run_id)
        result = await self.session.execute(
            query.order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc()).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def count_filtered(
        self,
        actions: Optional[Sequence[str]] = None,
        actor_agent: Optional[AgentName] = None,
        actor_user: Optional[str] = None,
        replay_run_id: Optional[str] = None
    ) -> int:
        """Count with the same filters as list_filtered()."""
        query = self._filtered(
            select(func.count()).select_from(AuditLog), actions, actor_agent, actor_user, replay_run_id
        )
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def count_by_action(self, replay_run_id: Optional[str] = None) -> dict[str, int]:
        """{action: count} for the Audit header tiles."""
        query = select(AuditLog.action, func.count()).group_by(AuditLog.action)
        if replay_run_id:
            query = query.where(AuditLog.replay_run_id == replay_run_id)
        result = await self.session.execute(query)
        return {action: count for action, count in result.tuples().all()}

    async def list_for_entity(self, entity_table: str, entity_id: str) -> Sequence[AuditLog]:
        """Audit trail of one record, oldest first."""
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.entity_table == entity_table, AuditLog.entity_id == entity_id)
            .order_by(AuditLog.occurred_at)
        )
        return result.scalars().all()

    async def get_latest_for_entity(self, entity_table: str, entity_id: str) -> Optional[AuditLog]:
        """Most recent audit record of one record (audit_id on API responses)."""
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.entity_table == entity_table, AuditLog.entity_id == entity_id)
            .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
