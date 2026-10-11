"""User API routes.

Endpoints:
    GET   /users           - List users (admin)
    POST  /users           - Create a user (admin)
    GET   /users/{user_id} - Get a user (admin, or the user themself)
    PATCH /users/{user_id} - Update a user (admin)
"""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from config.databases.postgresql import get_db
from app.middleware.auth_middleware import ADMIN_ROLES, get_current_user, require_role
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService
from app.schemas.auth_schema import CurrentUser
from app.schemas.common_schema import DEFAULT_LIMIT, MAX_LIMIT, UserRole
from app.schemas.user_schema import UserCreate, UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])
admin_user = require_role(*ADMIN_ROLES, action="manage users")


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    """Dependency: Create UserService with repository."""
    return UserService(UserRepository(db))


@router.get("", summary="List users", dependencies=[Depends(admin_user)])
async def get_users(
    role: Optional[UserRole] = Query(None, description="Role filter"),
    is_demo: Optional[bool] = Query(None, description="Demo user filter"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Maximum records to return"),
    service: UserService = Depends(get_user_service)
):
    """Paginated list of users ordered by display name."""
    return await service.get_users(role, is_demo, skip, limit)


@router.post("", summary="Create a user", dependencies=[Depends(admin_user)])
async def create_user(
    request: UserCreate,
    service: UserService = Depends(get_user_service)
):
    """Create a user. 409 if the email is taken."""
    return await service.create_user(request)


@router.get("/{user_id}", summary="Get a user by ID")
async def get_user(
    user_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: UserService = Depends(get_user_service)
):
    """Get a user. Admins can read anyone; other roles only themselves."""
    return await service.get_user(str(user_id), user)


@router.patch("/{user_id}", summary="Update a user", dependencies=[Depends(admin_user)])
async def update_user(
    user_id: UUID,
    request: UserUpdate,
    service: UserService = Depends(get_user_service)
):
    """Update the provided fields of a user."""
    return await service.update_user(str(user_id), request)
