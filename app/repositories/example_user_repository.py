"""Repository for ExampleUser entity."""
from typing import Optional, Sequence
from sqlalchemy import select
from app.repositories.base import BaseRepository
from app.models.example_user_model import ExampleUser


class ExampleUserRepository(BaseRepository[ExampleUser]):
    """Repository for ExampleUser CRUD operations."""
    model_class = ExampleUser
    
    async def email_exists(self, email: str, exclude_id: str = None) -> bool:
        """Check if email exists."""
        query = select(ExampleUser).where(ExampleUser.email == email)
        if exclude_id:
            query = query.where(ExampleUser.id != exclude_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None
    
    async def get_active_users(self, skip: int = 0, limit: int = 100) -> Sequence[ExampleUser]:
        """Get active users only."""
        result = await self.session.execute(
            select(ExampleUser)
            .where(ExampleUser.status == 1)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
