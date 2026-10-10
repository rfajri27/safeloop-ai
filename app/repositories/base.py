"""Base repository for data access.

Provides generic CRUD operations for SQLAlchemy models.
"""
from typing import TypeVar, Generic, Optional, Sequence, Type
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Base repository with generic CRUD operations.
    
    Usage:
        class UserRepository(BaseRepository[User]):
            model_class = User
    """
    model_class: Type[T]
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, entity: T) -> T:
        """Create a new entity."""
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return entity
    
    async def get_by_id(self, entity_id: str) -> Optional[T]:
        """Get entity by ID."""
        result = await self.session.execute(
            select(self.model_class).where(self.model_class.id == entity_id)
        )
        return result.scalar_one_or_none()
    
    async def get_all(self, skip: int = 0, limit: int = 100) -> Sequence[T]:
        """Get all entities with pagination."""
        result = await self.session.execute(
            select(self.model_class).offset(skip).limit(limit)
        )
        return result.scalars().all()
    
    async def update(self, entity: T) -> T:
        """Update an entity."""
        await self.session.commit()
        await self.session.refresh(entity)
        return entity
    
    async def delete(self, entity: T) -> None:
        """Delete an entity."""
        await self.session.delete(entity)
        await self.session.commit()
    
    async def count(self) -> int:
        """Count all entities."""
        result = await self.session.execute(
            select(func.count()).select_from(self.model_class)
        )
        return result.scalar() or 0
