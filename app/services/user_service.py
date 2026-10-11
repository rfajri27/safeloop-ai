"""User service for user management.

Endpoints served:
    GET   /users           - List users (admin)
    POST  /users           - Create a user (admin)
    GET   /users/{user_id} - Get a user (admin, or the user themself)
    PATCH /users/{user_id} - Update a user (admin)

There is no delete: users are referenced by the append-only audit log,
approvals and chat history.
"""
from typing import Optional
from fastapi.responses import JSONResponse
from app.models.user_model import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth_schema import CurrentUser
from app.schemas.common_schema import UserRole
from app.schemas.user_schema import UserCreate, UserResponse, UserUpdate
from app.utils.response import response_error, response_success


class UserService:
    """
    Service for User business logic.

    REQUEST-SCOPED: Created per request with injected repository.
    """

    def __init__(self, user_repository: UserRepository):
        """Initialize UserService with repository."""
        self.repo = user_repository

    async def get_users(
        self,
        role: Optional[UserRole] = None,
        is_demo: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50
    ) -> JSONResponse:
        """Get a paginated list of users; totals go in metadata."""
        users = await self.repo.list_filtered(role, is_demo, skip, limit)
        total = await self.repo.count_filtered(role, is_demo)

        return response_success(
            [UserResponse.model_validate(u).model_dump() for u in users],
            metadata={"total": total, "skip": skip, "limit": limit}
        )

    async def get_user(self, user_id: str, current_user: CurrentUser) -> JSONResponse:
        """Get a user by ID. Non-admins may only read their own record."""
        if current_user.role != UserRole.ADMIN and current_user.id != user_id:
            return response_error(
                f"Role {current_user.role.value} can only view its own user", code=403
            )

        user = await self.repo.get_by_id(user_id)
        if not user:
            return response_error(f"User {user_id} not found", code=404)

        return response_success(UserResponse.model_validate(user).model_dump())

    async def create_user(self, request: UserCreate) -> JSONResponse:
        """Create a user; 409 if the handle or email is taken."""
        if await self.repo.handle_exists(request.handle):
            return response_error(f"User with handle '{request.handle}' already exists", code=409)
        if request.email and await self.repo.email_exists(request.email):
            return response_error(f"User with email '{request.email}' already exists", code=409)

        user = User(
            handle=request.handle,
            display_name=request.display_name,
            email=request.email,
            role=request.role,
            is_demo=request.is_demo,
        )
        created_user = await self.repo.create(user)

        return response_success(
            UserResponse.model_validate(created_user).model_dump(),
            msg="Created",
            code=201
        )

    async def update_user(self, user_id: str, request: UserUpdate) -> JSONResponse:
        """Update the provided fields of a user; 404 if missing, 409 if the email is taken."""
        user = await self.repo.get_by_id(user_id)
        if not user:
            return response_error(f"User {user_id} not found", code=404)

        changes = request.model_dump(exclude_unset=True)
        for field in ("display_name", "role", "is_demo"):
            if changes.get(field) is None:
                changes.pop(field, None)

        if changes.get("email") and changes["email"] != user.email:
            if await self.repo.email_exists(changes["email"], exclude_id=user_id):
                return response_error(f"User with email '{changes['email']}' already exists", code=409)

        for field, value in changes.items():
            setattr(user, field, value)
        updated_user = await self.repo.update(user)

        return response_success(UserResponse.model_validate(updated_user).model_dump())
