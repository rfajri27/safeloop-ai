"""PostgreSQL database configuration and async session management.

This module provides:
- SINGLETON: AsyncEngine with connection pooling
- SINGLETON: async_sessionmaker for creating sessions
- REQUEST-SCOPED: get_db() dependency for async sessions
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from config.settings import env

DATABASE_URL = (
    f"postgresql+asyncpg://{env.db_user}:{env.db_pass}"
    f"@{env.db_host}:{env.db_port}/{env.db_name}"
)

# SINGLETON: Connection pool (created once at module import)
engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,      # Verify connection before use
    pool_recycle=3600,       # Recycle connections after 1 hour
    pool_size=10,            # Base pool size
    max_overflow=20,         # Allow up to 30 total connections
    echo=False,              # Disable SQL logging in production
)

# SINGLETON: Session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Prevent lazy loading issues
    autoflush=False,         # Manual flush for better control
)

# Base class for SQLAlchemy models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency: Request-scoped database session.
    
    Creates a new session for each request and ensures proper cleanup.
    Uses context manager for automatic session closing.
    
    Yields:
        AsyncSession: Database session for the current request
        
    Example:
        @router.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(User))
            return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise