"""Example User API routes.

This module provides RESTful endpoints for ExampleUser CRUD operations.
Routes are CLEAN - no try-except needed. Global handlers catch all errors.

Endpoints:
    POST   /example-users/          - Create a new user
    GET    /example-users/          - List all users
    GET    /example-users/{user_id} - Get a specific user
    PUT    /example-users/{user_id} - Update a user
    DELETE /example-users/{user_id} - Delete a user (soft delete)
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from config.databases.postgresql import get_db
from app.repositories.example_user_repository import ExampleUserRepository
from app.services.example_user_service import ExampleUserService
from app.schemas.example_user_schema import ExampleUserCreate, ExampleUserUpdate

router = APIRouter(prefix="/example-users", tags=["Example: User CRUD"])


def get_user_service(db: AsyncSession = Depends(get_db)) -> ExampleUserService:
    """Dependency: Create ExampleUserService with repository."""
    repo = ExampleUserRepository(db)
    return ExampleUserService(repo)


@router.post("/", summary="Create a new user")
async def create_user(
    request: ExampleUserCreate,
    service: ExampleUserService = Depends(get_user_service)
):
    """Create a new user."""
    return await service.create_user(
        name=request.name,
        email=request.email,
        role=request.role
    )


@router.get("/", summary="List all users")
async def get_users(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500,
                       description="Maximum records to return"),
    active_only: bool = Query(True, description="Return only active users"),
    service: ExampleUserService = Depends(get_user_service)
):
    """Get paginated list of users."""
    return await service.get_users(skip, limit, active_only)


@router.get("/{user_id}", summary="Get a user by ID")
async def get_user(
    user_id: str,
    service: ExampleUserService = Depends(get_user_service)
):
    """Get a specific user by ID."""
    return await service.get_user(user_id)


@router.put("/{user_id}", summary="Update a user")
async def update_user(
    user_id: str,
    request: ExampleUserUpdate,
    service: ExampleUserService = Depends(get_user_service)
):
    """Update an existing user."""
    return await service.update_user(
        user_id=user_id,
        name=request.name,
        email=request.email,
        role=request.role,
        status=request.status
    )


@router.delete("/{user_id}", summary="Delete a user")
async def delete_user(
    user_id: str,
    service: ExampleUserService = Depends(get_user_service)
):
    """Soft delete a user (sets status to inactive)."""
    return await service.delete_user(user_id)
