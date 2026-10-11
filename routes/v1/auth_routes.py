"""Auth API routes.

Endpoints:
    POST /auth/demo-login - JWT for a seeded demo user (public)
    GET  /auth/me         - Current user and role
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from config.databases.postgresql import get_db
from app.middleware.auth_middleware import get_current_user
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.schemas.auth_schema import CurrentUser, DemoLoginRequest

router = APIRouter(prefix="/auth", tags=["Auth"])


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    """Dependency: Create AuthService with repository."""
    return AuthService(UserRepository(db))


@router.post("/demo-login", summary="Log in as a seeded demo user")
async def demo_login(
    request: DemoLoginRequest,
    service: AuthService = Depends(get_auth_service)
):
    """Return a JWT for rina, dimas, agus, auditor or admin."""
    return await service.demo_login(request.user)


@router.get("/me", summary="Get the current user")
async def get_me(
    user: CurrentUser = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service)
):
    """Return the current user and role."""
    return await service.get_me(user)
