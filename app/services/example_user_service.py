"""Example User service for business logic.

This module provides ExampleUserService with User-related business operations.

HTTP Status Code Standard:
    200 - Success (all success responses)
    400 - Client error (validation, not found, conflict)
    401 - Unauthorized (auth required)
    500 - Server error (unexpected errors)
"""
from typing import Optional, Sequence
from fastapi.responses import JSONResponse
from app.repositories.example_user_repository import ExampleUserRepository
from app.models.example_user_model import ExampleUser
from app.schemas.example_user_schema import ExampleUserResponse, ExampleUserListResponse
from app.utils.response import response_success, response_error


class ExampleUserService:
    """
    Service for ExampleUser business logic.
    
    REQUEST-SCOPED: Created per request with injected repository.
    """
    
    # Valid user roles
    VALID_ROLES = ("user", "admin", "superadmin")
    
    def __init__(self, user_repository: ExampleUserRepository):
        """Initialize ExampleUserService with repository."""
        self.repo = user_repository
    
    async def create_user(
        self,
        name: str,
        email: str,
        role: str = "user"
    ) -> JSONResponse:
        """Create a new user."""
        # Validate role
        if role not in self.VALID_ROLES:
            return response_error(
                f"Invalid role: {role}. Valid roles: {', '.join(self.VALID_ROLES)}"
            )
        
        # Check if email already exists
        if await self.repo.email_exists(email):
            return response_error(f"User with email '{email}' already exists")
        
        # Create user
        user = ExampleUser(name=name, email=email, role=role)
        created_user = await self.repo.create(user)
        
        return response_success(
            ExampleUserResponse.model_validate(created_user).model_dump(),
            msg="User created successfully"
        )
    
    async def get_user(self, user_id: str) -> JSONResponse:
        """Get a user by ID."""
        user = await self.repo.get_by_id(user_id)
        if not user:
            return response_error(f"User with id '{user_id}' not found")
        
        return response_success(
            ExampleUserResponse.model_validate(user).model_dump()
        )
    
    async def get_users(
        self,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = True
    ) -> JSONResponse:
        """Get paginated list of users."""
        if active_only:
            users = await self.repo.get_active_users(skip, limit)
        else:
            users = await self.repo.get_all(skip, limit)
        total = await self.repo.count()
        
        return response_success(
            ExampleUserListResponse(
                items=[ExampleUserResponse.model_validate(u) for u in users],
                total=total,
                skip=skip,
                limit=limit
            ).model_dump()
        )
    
    async def update_user(
        self,
        user_id: str,
        name: Optional[str] = None,
        email: Optional[str] = None,
        role: Optional[str] = None,
        status: Optional[int] = None
    ) -> JSONResponse:
        """Update a user."""
        # Get existing user
        user = await self.repo.get_by_id(user_id)
        if not user:
            return response_error(f"User with id '{user_id}' not found")
        
        # Validate role if provided
        if role is not None and role not in self.VALID_ROLES:
            return response_error(
                f"Invalid role: {role}. Valid roles: {', '.join(self.VALID_ROLES)}"
            )
        
        # Check email uniqueness if changing email
        if email is not None and email != user.email:
            if await self.repo.email_exists(email, exclude_id=user_id):
                return response_error(f"User with email '{email}' already exists")
            user.email = email
        
        # Update fields if provided
        if name is not None:
            user.name = name
        if role is not None:
            user.role = role
        if status is not None:
            user.status = status
        
        updated_user = await self.repo.update(user)
        
        return response_success(
            ExampleUserResponse.model_validate(updated_user).model_dump(),
            msg="User updated successfully"
        )
    
    async def delete_user(self, user_id: str) -> JSONResponse:
        """Soft delete a user (set status to 0)."""
        user = await self.repo.get_by_id(user_id)
        if not user:
            return response_error(f"User with id '{user_id}' not found")
        
        user.status = 0
        await self.repo.update(user)
        
        return response_success(None, msg="User deleted successfully")
