"""Repository for Citation entity (polymorphic evidence links)."""
from typing import Optional, Sequence
from sqlalchemy import select
from app.repositories.base import BaseRepository
from app.models.citation_model import Citation


class CitationRepository(BaseRepository[Citation]):
    """Repository for Citation queries.

    Each citation has exactly one owner: chat message, proposal, approval
    item or re-score.
    """
    model_class = Citation

    async def list_by_owner(
        self,
        chat_message_id: Optional[str] = None,
        proposal_id: Optional[str] = None,
        approval_item_id: Optional[str] = None,
        rescore_id: Optional[str] = None,
        resolved_only: bool = False
    ) -> Sequence[Citation]:
        """Citations of one owner. Pass exactly one owner id."""
        owners = {
            Citation.chat_message_id: chat_message_id,
            Citation.proposal_id: proposal_id,
            Citation.approval_item_id: approval_item_id,
            Citation.rescore_id: rescore_id,
        }
        given = [(column, value) for column, value in owners.items() if value is not None]
        if len(given) != 1:
            raise ValueError("Pass exactly one owner id")
        column, value = given[0]
        query = select(Citation).where(column == value)
        if resolved_only:
            query = query.where(Citation.resolved.is_(True))
        result = await self.session.execute(query)
        return result.scalars().all()

    async def list_by_chat_messages(self, chat_message_ids: Sequence[str]) -> Sequence[Citation]:
        """Citations for several chat messages (session history)."""
        if not chat_message_ids:
            return []
        result = await self.session.execute(
            select(Citation).where(Citation.chat_message_id.in_(chat_message_ids))
        )
        return result.scalars().all()

    async def list_by_proposals(self, proposal_ids: Sequence[str]) -> Sequence[Citation]:
        """Citations for several proposals (a Red Team run)."""
        if not proposal_ids:
            return []
        result = await self.session.execute(
            select(Citation).where(Citation.proposal_id.in_(proposal_ids))
        )
        return result.scalars().all()

    async def cited_chunk_ids(self, chunk_ids: Sequence[str]) -> set[str]:
        """Which of the given chunks some citation points at (they must not be deleted)."""
        if not chunk_ids:
            return set()
        result = await self.session.execute(
            select(Citation.chunk_id).where(Citation.chunk_id.in_(chunk_ids)).distinct()
        )
        return set(result.scalars().all())
