"""Repository for User entity."""
from typing import Optional, Sequence
from sqlalchemy import func, select
from app.repositories.base import BaseRepository
from app.models.enums import UserRole
from app.models.user_model import User


class UserRepository(BaseRepository[User]):
    """Repository for User queries."""
    model_class = User

    def _filtered(self, query, role: Optional[UserRole], is_demo: Optional[bool]):
        if role:
            query = query.where(User.role == role)
        if is_demo is not None:
            query = query.where(User.is_demo.is_(is_demo))
        return query

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get a user by email."""
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def email_exists(self, email: str, exclude_id: Optional[str] = None) -> bool:
        """Check if an email is taken (case-insensitive), optionally ignoring one user."""
        query = select(User.id).where(func.lower(User.email) == email.lower())
        if exclude_id:
            query = query.where(User.id != exclude_id)
        result = await self.session.execute(query.limit(1))
        return result.scalar_one_or_none() is not None

    async def handle_exists(self, handle: str) -> bool:
        """Check if a login handle is taken."""
        result = await self.session.execute(select(User.id).where(User.handle == handle.lower()).limit(1))
        return result.scalar_one_or_none() is not None

    async def list_filtered(
        self,
        role: Optional[UserRole] = None,
        is_demo: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50
    ) -> Sequence[User]:
        """List users ordered by display name."""
        query = self._filtered(select(User), role, is_demo)
        result = await self.session.execute(
            query.order_by(User.display_name, User.id).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def count_filtered(self, role: Optional[UserRole] = None, is_demo: Optional[bool] = None) -> int:
        """Count with the same filters as list_filtered()."""
        query = self._filtered(select(func.count()).select_from(User), role, is_demo)
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def get_demo_user(self, handle: str) -> Optional[User]:
        """Get a seeded demo user by handle (rina, dimas, ...)."""
        result = await self.session.execute(
            select(User).where(
                User.is_demo.is_(True),
                User.handle == handle.lower(),
            )
        )
        return result.scalar_one_or_none()

    async def list_by_role(self, role: UserRole) -> Sequence[User]:
        """Users with a role."""
        result = await self.session.execute(
            select(User).where(User.role == role).order_by(User.display_name)
        )
        return result.scalars().all()
