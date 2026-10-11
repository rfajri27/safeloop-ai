"""Auth service for demo login and the current user.

Endpoints served:
    POST /auth/demo-login - JWT for a seeded demo user
    GET  /auth/me         - Current user and role
"""
from fastapi.responses import JSONResponse
from config.settings import env
from app.repositories.user_repository import UserRepository
from app.schemas.auth_schema import CurrentUser
from app.schemas.user_schema import UserResponse
from app.utils.jwt_utils import JwtUtils
from app.utils.response import response_error, response_success


class AuthService:
    """
    Service for demo authentication. There is no password store in the MVP.

    REQUEST-SCOPED: Created per request with injected repository.
    """

    def __init__(self, user_repository: UserRepository):
        """Initialize AuthService with repository."""
        self.repo = user_repository

    async def demo_login(self, user_handle: str) -> JSONResponse:
        """Issue an HS256 JWT (sub, role, name) for a seeded demo user; 404 if unknown."""
        user = await self.repo.get_demo_user(user_handle)
        if not user:
            return response_error(f"Demo user '{user_handle}' not found", code=404)

        token = JwtUtils.create_access_token({
            "sub": user.id,
            "role": user.role.value,
            "name": user.display_name,
        })

        return response_success({
            "access_token": token,
            "token_type": "bearer",
            "expires_in": env.jwt_expire_minutes * 60,
            "user": {
                "id": user.id,
                "display_name": user.display_name,
                "role": user.role.value,
            },
        })

    async def get_me(self, user: CurrentUser) -> JSONResponse:
        """Return the current user's record; 401 if the token's user no longer exists."""
        record = await self.repo.get_by_id(user.id)
        if not record:
            return response_error("Not authenticated", code=401)

        return response_success(UserResponse.model_validate(record).model_dump())
